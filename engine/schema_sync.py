import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from engine.crypto import decrypt_password
from engine.datasource import MOCK_TABLES_INFO, get_mysql_connection_params, is_demo_db
from engine.models import DataSource, SchemaColumn, SchemaTable


def sync_schema(db: Session, datasource_id: str) -> dict[str, Any]:
    """
    Synchronize tables and columns metadata from the target MySQL (or Demo DB)
    into the local SQLite metadata database.
    Does it in three distinct phases:
    1. Synchronize all tables.
    2. Synchronize all columns & primary keys.
    3. Backfill foreign key relationships.
    """
    ds = db.query(DataSource).filter(DataSource.id == datasource_id).first()
    if not ds:
        raise ValueError("Data source not found")

    try:
        # Clear existing schema metadata for this data source to ensure a clean sync
        table_ids = [t.id for t in ds.tables]
        if table_ids:
            db.query(SchemaColumn).filter(SchemaColumn.table_id.in_(table_ids)).delete(synchronize_session=False)
        db.query(SchemaTable).filter(SchemaTable.data_source_id == datasource_id).delete(synchronize_session=False)
        db.commit()

        tables_to_insert = []
        columns_to_insert = []
        
        # 1. Gather schema metadata (Demo DB vs Real DB)
        if is_demo_db(str(ds.host), str(ds.database_name)):
            # Built-in Demo Schema
            for t_info in MOCK_TABLES_INFO:
                table_id = str(uuid.uuid4())
                t_obj = SchemaTable(
                    id=table_id,
                    data_source_id=datasource_id,
                    table_schema=ds.database_name,
                    table_name=t_info["table_name"],
                    table_comment=t_info["table_comment"],
                    table_type=t_info["table_type"],
                    row_count_estimate=t_info["row_count_estimate"],
                    engine_name=t_info["engine_name"]
                )
                tables_to_insert.append(t_obj)
                
                # Keep trace of table_id mapping for columns
                t_info["temp_id"] = table_id

            # Save tables first so we can reference them
            for t in tables_to_insert:
                db.add(t)
            db.commit()

            # Now add columns and map keys
            for t_info in MOCK_TABLES_INFO:
                table_id = str(t_info["temp_id"])
                columns_list: list[dict[str, object]] = t_info["columns"]  # type: ignore[assignment]
                for i, col in enumerate(columns_list):
                    demo_col_id = str(uuid.uuid4())
                    c_obj = SchemaColumn(
                        id=demo_col_id,
                        table_id=table_id,
                        column_name=col["column_name"],
                        data_type=col["data_type"],
                        column_type=col["column_type"],
                        is_nullable=col["is_nullable"],
                        column_default=None,
                        column_comment=col["column_comment"],
                        is_primary_key=col["is_primary_key"],
                        is_foreign_key=col.get("is_foreign_key", 0),
                        ordinal_position=i + 1
                    )
                    columns_to_insert.append(c_obj)
                    
                    # Store col_id for relationship linking
                    col["temp_id"] = demo_col_id

            for c in columns_to_insert:
                db.add(c)
            db.commit()

            # Backfill foreign key relationships in Demo mode
            for t_info in MOCK_TABLES_INFO:
                fk_columns: list[dict[str, object]] = t_info["columns"]  # type: ignore[assignment]
                for col in fk_columns:
                    if col.get("is_foreign_key"):
                        target_tbl_name = col["foreign_table"]
                        target_col_name = col["foreign_column"]
                        
                        # Find the target table in DB
                        target_table = db.query(SchemaTable).filter(
                            SchemaTable.data_source_id == datasource_id,
                            SchemaTable.table_name == target_tbl_name
                        ).first()
                        
                        if target_table:
                            # Find the target column in DB
                            target_column = db.query(SchemaColumn).filter(
                                SchemaColumn.table_id == target_table.id,
                                SchemaColumn.column_name == target_col_name
                            ).first()
                            
                            if target_column:
                                db.query(SchemaColumn).filter(SchemaColumn.id == col["temp_id"]).update({
                                    "foreign_table_id": target_table.id,
                                    "foreign_column_id": target_column.id
                                })
            db.commit()

        else:
            # Real DB Schema Sync using SQLAlchemy inspector
            _host = str(ds.host)
            _port = int(ds.port)
            _user = str(ds.username)
            _db = str(ds.database_name)
            pw = decrypt_password(str(ds.password_ciphertext), str(ds.password_nonce))
            dsn = URL.create(
                drivername="mysql+pymysql",
                username=_user,
                password=pw,
                host=_host,
                port=_port,
                database=_db,
                query={"charset": "utf8mb4"},
            )
            engine = create_engine(dsn, connect_args={"connect_timeout": 5})
            
            try:
                inspector = inspect(engine)
                
                # Fetch tables
                table_names = inspector.get_table_names()
                view_names = inspector.get_view_names()
                
                all_tables = [(name, "BASE TABLE") for name in table_names] + [(name, "VIEW") for name in view_names]
                
                table_name_to_id = {}
                
                # 1. Insert all tables
                for name, t_type in all_tables:
                    # Try to fetch comment or row counts estimate if possible
                    comment = None
                    try:
                        comment = inspector.get_table_comment(name).get("text")
                    except Exception:
                        pass
                    
                    table_id = str(uuid.uuid4())
                    t_obj = SchemaTable(
                        id=table_id,
                        data_source_id=datasource_id,
                        table_schema=ds.database_name,
                        table_name=name,
                        table_comment=comment,
                        table_type=t_type,
                        row_count_estimate=0, # Estimated row count can be updated later
                        engine_name="InnoDB" if t_type == "BASE TABLE" else None
                    )
                    db.add(t_obj)
                    table_name_to_id[name] = table_id
                
                db.commit()
                
                # 2. Insert all columns
                column_name_to_id = {} # Keyed by (table_name, column_name) -> col_id
                
                for name, t_type in all_tables:
                    table_id = table_name_to_id[name]
                    
                    # Columns and primary keys
                    columns = inspector.get_columns(name)
                    pk_cols = inspector.get_pk_constraint(name).get("constrained_columns", [])

                    for i, col in enumerate(columns):  # type: ignore[assignment]
                        col_id = str(uuid.uuid4())
                        c_name = str(col["name"])
                        column_name_to_id[(name, c_name)] = col_id
                        
                        is_nullable_val = col.get("nullable", True)
                        is_pk = c_name in pk_cols
                        
                        c_obj = SchemaColumn(
                            id=col_id,
                            table_id=table_id,
                            column_name=c_name,
                            data_type=str(col["type"]).split("(")[0].lower(),
                            column_type=str(col["type"]),
                            is_nullable=is_nullable_val,
                            column_default=str(col["default"]) if col.get("default") is not None else None,
                            column_comment=col.get("comment"),
                            is_primary_key=is_pk,
                            is_foreign_key=0, # will backfill in next step
                            ordinal_position=i + 1
                        )
                        db.add(c_obj)
                
                db.commit()
                
                # 3. Backfill Foreign Keys
                for name, t_type in all_tables:
                    table_id = table_name_to_id[name]
                    fkeys = inspector.get_foreign_keys(name)
                    
                    for fk in fkeys:
                        constrained_cols: list[str] = fk.get("constrained_columns", [])
                        referred_table: str | None = fk.get("referred_table")
                        referred_cols: list[str] = fk.get("referred_columns", [])

                        if len(constrained_cols) == 1 and len(referred_cols) == 1 and referred_table is not None:
                            col_name: str = constrained_cols[0]
                            ref_col_name: str = referred_cols[0]

                            fk_col_id = column_name_to_id.get((name, col_name))
                            ref_table_id_fk = table_name_to_id.get(referred_table)
                            ref_col_id_fk = column_name_to_id.get((referred_table, ref_col_name))

                            if fk_col_id and ref_table_id_fk and ref_col_id_fk:
                                db.query(SchemaColumn).filter(SchemaColumn.id == fk_col_id).update({
                                    "is_foreign_key": True,
                                    "foreign_table_id": ref_table_id_fk,
                                    "foreign_column_id": ref_col_id_fk
                                })
                
                db.commit()
            finally:
                engine.dispose()

        # Update sync stats in data_sources
        now = datetime.now(UTC)
        db.query(DataSource).filter(DataSource.id == datasource_id).update({
            "last_sync_at": now,
            "last_sync_status": "success",
            "last_sync_error": None
        })
        db.commit()

        return {
            "ok": True,
            "tablesSynced": len(tables_to_insert) if is_demo_db(str(ds.host), str(ds.database_name)) else len(all_tables),
            "message": "元数据结构同步成功！"
        }

    except Exception as e:
        now = datetime.now(UTC)
        db.query(DataSource).filter(DataSource.id == datasource_id).update({
            "last_sync_at": now,
            "last_sync_status": "failed",
            "last_sync_error": str(e)
        })
        db.commit()
        raise ValueError(f"结构同步发生错误: {str(e)}")

def build_er_diagram_data(db: Session, datasource_id: str) -> dict[str, Any]:
    """
    Constructs ER diagram node and link data based on synchronized tables & columns in SQLite
    for rendering with React Flow or simple visualizations.
    """
    tables = db.query(SchemaTable).filter(SchemaTable.data_source_id == datasource_id).all()
    
    nodes = []
    edges = []
    
    table_id_to_name = {t.id: t.table_name for t in tables}
    
    for t in tables:
        fields = []
        for col in t.columns:
            fields.append({
                "name": col.column_name,
                "type": col.column_type,
                "is_pk": bool(col.is_primary_key),
                "is_fk": bool(col.is_foreign_key),
                "comment": col.column_comment
            })
            
            # If foreign key, generate an edge
            if col.is_foreign_key and col.foreign_table_id:
                target_table_name = table_id_to_name.get(col.foreign_table_id)
                target_col = db.query(SchemaColumn).filter(SchemaColumn.id == col.foreign_column_id).first()
                target_col_name = target_col.column_name if target_col else "id"
                
                if target_table_name:
                    edges.append({
                        "id": f"fk-{t.table_name}-{col.column_name}__to__{target_table_name}-{target_col_name}",
                        "source": t.table_name,
                        "sourceHandle": col.column_name,
                        "target": target_table_name,
                        "targetHandle": target_col_name,
                        "label": "FK"
                    })
                    
        nodes.append({
            "id": t.table_name,
            "label": t.table_name,
            "comment": t.table_comment or "",
            "fields": fields
        })
        
    return {
        "nodes": nodes,
        "edges": edges
    }
