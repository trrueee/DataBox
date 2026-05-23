import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from engine.ai import generate_sql
from engine.crypto import encrypt_password
from engine.datasource import test_connection
from engine.db import get_db
from engine.errors import DataBoxError
from engine.executor import execute_query
from engine.guardrail import guardrail_check
from engine.models import DataSource, QueryHistory, SchemaTable
from engine.schema_sync import build_er_diagram_data, sync_schema

logger = logging.getLogger("databox.api")
router = APIRouter(prefix="/api/v1")


class DataSourceTestRequest(BaseModel):
    host: str
    port: int = 3306
    database_name: str
    username: str
    password: str


class DataSourceCreateRequest(BaseModel):
    name: str
    host: str
    port: int = 3306
    database_name: str
    username: str
    password: str
    connection_mode: str = "direct"


class SQLValidateRequest(BaseModel):
    sql: str


class SQLExecuteRequest(BaseModel):
    datasource_id: str
    sql: str
    question: str | None = None


class SQLGenerateRequest(BaseModel):
    datasource_id: str
    question: str
    api_key: str | None = None
    api_base: str | None = None
    model_name: str | None = None


def _datasource_to_dict(ds: DataSource) -> dict[str, Any]:
    return {
        "id": ds.id,
        "name": ds.name,
        "host": ds.host,
        "port": ds.port,
        "database_name": ds.database_name,
        "username": ds.username,
        "connection_mode": ds.connection_mode,
        "status": ds.status,
        "last_test_at": ds.last_test_at.isoformat() if ds.last_test_at else None,
        "last_test_status": ds.last_test_status,
        "last_test_error": ds.last_test_error,
        "last_sync_at": ds.last_sync_at.isoformat() if ds.last_sync_at else None,
        "last_sync_status": ds.last_sync_status,
        "last_sync_error": ds.last_sync_error,
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
    }


@router.post("/datasources/test")
def api_test_connection(req: DataSourceTestRequest) -> dict[str, Any]:
    try:
        return test_connection(req.model_dump())
    except DataBoxError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)})
    except Exception as exc:
        logger.exception("Connection test failed")
        raise HTTPException(status_code=400, detail={"code": "CONNECTION_FAILED", "message": "数据库连接测试失败，请检查连接配置。"})


@router.post("/datasources")
def api_create_datasource(req: DataSourceCreateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        cipher, nonce = encrypt_password(req.password)
        datasource = DataSource(
            id=str(uuid.uuid4()),
            name=req.name,
            host=req.host,
            port=req.port,
            database_name=req.database_name,
            username=req.username,
            password_ciphertext=cipher,
            password_nonce=nonce,
            connection_mode=req.connection_mode,
            status="active",
        )
        db.add(datasource)
        db.commit()
        db.refresh(datasource)
        return _datasource_to_dict(datasource)
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to create datasource")
        raise HTTPException(
            status_code=500,
            detail={"code": "DATASOURCE_CREATE_FAILED", "message": "创建数据源失败，请稍后重试。"},
        )


@router.get("/datasources")
def api_list_datasources(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [_datasource_to_dict(ds) for ds in db.query(DataSource).all()]


@router.delete("/datasources/{id}")
def api_delete_datasource(id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    datasource = db.query(DataSource).filter(DataSource.id == id).first()
    if not datasource:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "数据源不存在"})

    try:
        db.delete(datasource)
        db.commit()
        return {"success": True, "message": "数据源已删除"}
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to delete datasource")
        raise HTTPException(
            status_code=500,
            detail={"code": "DATASOURCE_DELETE_FAILED", "message": "删除数据源失败，请稍后重试。"},
        )


@router.post("/datasources/{id}/sync")
def api_sync_schema(id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return sync_schema(db, id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "SYNC_FAILED", "message": str(exc)})
    except Exception as exc:
        logger.exception("Schema sync failed")
        raise HTTPException(
            status_code=500,
            detail={"code": "SYNC_FAILED", "message": "元数据结构同步失败，请检查数据库连接后重试。"},
        )


@router.get("/schema/tables")
def api_list_tables(datasource_id: str = Query(...), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    tables = db.query(SchemaTable).filter(SchemaTable.data_source_id == datasource_id).all()
    return [
        {
            "id": table.id,
            "table_name": table.table_name,
            "table_comment": table.table_comment or "",
            "table_type": table.table_type,
            "row_count_estimate": table.row_count_estimate,
            "columns_count": len(table.columns),
        }
        for table in tables
    ]


@router.get("/schema/tables/{table_id}/columns")
def api_list_columns(table_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    table = db.query(SchemaTable).filter(SchemaTable.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "表结构记录不存在"})

    return [
        {
            "id": column.id,
            "column_name": column.column_name,
            "data_type": column.data_type,
            "column_type": column.column_type,
            "is_nullable": bool(column.is_nullable),
            "column_default": column.column_default or "",
            "column_comment": column.column_comment or "",
            "is_primary_key": bool(column.is_primary_key),
            "is_foreign_key": bool(column.is_foreign_key),
            "foreign_table_id": column.foreign_table_id,
            "foreign_column_id": column.foreign_column_id,
        }
        for column in table.columns
    ]


@router.get("/schema/er-diagram")
def api_get_er_diagram(datasource_id: str = Query(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return build_er_diagram_data(db, datasource_id)
    except Exception as exc:
        logger.exception("ER diagram build failed")
        raise HTTPException(
            status_code=500,
            detail={"code": "DIAGRAM_FAILED", "message": "生成 ER 图失败，请确认已完成 Schema 同步。"},
        )


@router.post("/query/validate")
def api_validate_sql(req: SQLValidateRequest) -> dict[str, Any]:
    result = guardrail_check(req.sql)
    return dict(result)


@router.post("/query/execute")
def api_execute_sql(req: SQLExecuteRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return execute_query(db, req.datasource_id, req.sql, req.question)
    except DataBoxError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)})
    except Exception as exc:
        logger.exception("SQL execution failed")
        raise HTTPException(
            status_code=500,
            detail={"code": "EXECUTION_ERROR", "message": "SQL 执行失败，请检查语句是否正确。"},
        )


@router.get("/query/history")
def api_query_history(datasource_id: str = Query(...), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    history = (
        db.query(QueryHistory)
        .filter(QueryHistory.data_source_id == datasource_id)
        .order_by(QueryHistory.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": item.id,
            "question": item.question or "",
            "submitted_sql": item.submitted_sql,
            "generated_sql": item.generated_sql or "",
            "safe_sql": item.safe_sql or "",
            "executed_sql": item.executed_sql or "",
            "guardrail_result": item.guardrail_result,
            "execution_status": item.execution_status,
            "execution_time_ms": item.execution_time_ms or 0,
            "rows_returned": item.rows_returned or 0,
            "columns_returned": item.columns_returned or 0,
            "error_message": item.error_message or "",
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in history
    ]


@router.post("/query/generate")
def api_generate_sql(req: SQLGenerateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        llm_config = {}
        if req.api_key:
            llm_config = {
                "api_key": req.api_key,
                "api_base": req.api_base or "https://api.openai.com/v1",
                "model": req.model_name or "gpt-4o-mini",
            }
        return generate_sql(db, req.datasource_id, req.question, llm_config)
    except DataBoxError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)})
    except Exception as exc:
        logger.exception("SQL generation failed")
        raise HTTPException(
            status_code=500,
            detail={"code": "GENERATION_ERROR", "message": "AI 生成 SQL 失败，请检查模型配置或稍后重试。"},
        )
