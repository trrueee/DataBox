"""add_unique_constraints

Revision ID: a3d7346c7b53
Revises: 99b4fdab0781
Create Date: 2026-05-24 20:29:23.804312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3d7346c7b53'
down_revision: Union[str, Sequence[str], None] = '99b4fdab0781'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema and perform duplicate cleanup first."""
    bind = op.get_bind()

    # 1. Deduplicate projects on 'name'
    proj_rows = bind.execute(sa.text(
        "SELECT name, COUNT(*) as c FROM projects GROUP BY name HAVING c > 1"
    )).fetchall()
    for name, _ in proj_rows:
        proj_ids = [r[0] for r in bind.execute(sa.text(
            "SELECT id FROM projects WHERE name = :name ORDER BY created_at ASC"
        ), {"name": name}).fetchall()]
        kept_id = proj_ids[0]
        duplicate_ids = proj_ids[1:]
        if duplicate_ids:
            placeholders = ",".join(f":id_{i}" for i in range(len(duplicate_ids)))
            params = {f"id_{i}": val for i, val in enumerate(duplicate_ids)}
            params["kept_id"] = kept_id
            
            bind.execute(sa.text(f"UPDATE data_sources SET project_id = :kept_id WHERE project_id IN ({placeholders})"), params)
            bind.execute(sa.text(f"UPDATE database_environments SET project_id = :kept_id WHERE project_id IN ({placeholders})"), params)
            bind.execute(sa.text(f"UPDATE backup_records SET project_id = :kept_id WHERE project_id IN ({placeholders})"), params)
            bind.execute(sa.text(f"UPDATE table_design_drafts SET project_id = :kept_id WHERE project_id IN ({placeholders})"), params)
            
            bind.execute(sa.text(f"DELETE FROM projects WHERE id IN ({placeholders})"), {f"id_{i}": val for i, val in enumerate(duplicate_ids)})

    # 2. Deduplicate data_sources on 'project_id' and 'name'
    ds_rows = bind.execute(sa.text(
        "SELECT project_id, name, COUNT(*) as c FROM data_sources GROUP BY project_id, name HAVING c > 1"
    )).fetchall()
    for row in ds_rows:
        project_id, ds_name = row[0], row[1]
        ds_id_rows = bind.execute(sa.text(
            "SELECT id FROM data_sources WHERE project_id = :project_id AND name = :name ORDER BY created_at ASC"
        ), {"project_id": project_id, "name": ds_name}).fetchall()
        ds_ids = [r[0] for r in ds_id_rows]
        kept_id = ds_ids[0]
        duplicate_ids = ds_ids[1:]
        if duplicate_ids:
            placeholders = ",".join(f":id_{i}" for i in range(len(duplicate_ids)))
            params = {f"id_{i}": val for i, val in enumerate(duplicate_ids)}
            params["kept_id"] = kept_id
            
            bind.execute(sa.text(f"UPDATE schema_tables SET data_source_id = :kept_id WHERE data_source_id IN ({placeholders})"), params)
            bind.execute(sa.text(f"UPDATE query_history SET data_source_id = :kept_id WHERE data_source_id IN ({placeholders})"), params)
            bind.execute(sa.text(f"UPDATE golden_sqls SET data_source_id = :kept_id WHERE data_source_id IN ({placeholders})"), params)
            bind.execute(sa.text(f"UPDATE backup_records SET data_source_id = :kept_id WHERE data_source_id IN ({placeholders})"), params)
            
            bind.execute(sa.text(f"DELETE FROM data_sources WHERE id IN ({placeholders})"), {f"id_{i}": val for i, val in enumerate(duplicate_ids)})

    # 3. Deduplicate schema_tables on 'data_source_id', 'table_schema', and 'table_name'
    st_rows = bind.execute(sa.text(
        "SELECT data_source_id, table_schema, table_name, COUNT(*) as c FROM schema_tables GROUP BY data_source_id, table_schema, table_name HAVING c > 1"
    )).fetchall()
    for row in st_rows:
        ds_id, t_schema, t_name = row[0], row[1], row[2]
        t_rows = bind.execute(sa.text(
            "SELECT id FROM schema_tables WHERE data_source_id = :ds_id AND table_schema = :t_schema AND table_name = :t_name ORDER BY created_at ASC"
        ), {"ds_id": ds_id, "t_schema": t_schema, "t_name": t_name}).fetchall()
        t_ids = [r[0] for r in t_rows]
        kept_id = t_ids[0]
        duplicate_ids = t_ids[1:]
        if duplicate_ids:
            placeholders = ",".join(f":id_{i}" for i in range(len(duplicate_ids)))
            params = {f"id_{i}": val for i, val in enumerate(duplicate_ids)}
            params["kept_id"] = kept_id
            
            bind.execute(sa.text(f"UPDATE schema_columns SET table_id = :kept_id WHERE table_id IN ({placeholders})"), params)
            bind.execute(sa.text(f"DELETE FROM schema_tables WHERE id IN ({placeholders})"), {f"id_{i}": val for i, val in enumerate(duplicate_ids)})

    # 4. Deduplicate schema_columns on 'table_id' and 'column_name'
    sc_rows = bind.execute(sa.text(
        "SELECT table_id, column_name, COUNT(*) as c FROM schema_columns GROUP BY table_id, column_name HAVING c > 1"
    )).fetchall()
    for row in sc_rows:
        table_id, c_name = row[0], row[1]
        c_rows = bind.execute(sa.text(
            "SELECT id FROM schema_columns WHERE table_id = :table_id AND column_name = :c_name ORDER BY created_at ASC"
        ), {"table_id": table_id, "c_name": c_name}).fetchall()
        c_ids = [r[0] for r in c_rows]
        duplicate_ids = c_ids[1:]
        if duplicate_ids:
            placeholders = ",".join(f":id_{i}" for i in range(len(duplicate_ids)))
            bind.execute(sa.text(f"DELETE FROM schema_columns WHERE id IN ({placeholders})"), {f"id_{i}": val for i, val in enumerate(duplicate_ids)})

    # 5. Deduplicate golden_sqls on 'data_source_id' and 'question'
    gs_rows = bind.execute(sa.text(
        "SELECT data_source_id, question, COUNT(*) as c FROM golden_sqls GROUP BY data_source_id, question HAVING c > 1"
    )).fetchall()
    for row in gs_rows:
        ds_id, question = row[0], row[1]
        g_rows = bind.execute(sa.text(
            "SELECT id FROM golden_sqls WHERE data_source_id = :ds_id AND question = :question ORDER BY created_at ASC"
        ), {"ds_id": ds_id, "question": question}).fetchall()
        g_ids = [r[0] for r in g_rows]
        duplicate_ids = g_ids[1:]
        if duplicate_ids:
            placeholders = ",".join(f":id_{i}" for i in range(len(duplicate_ids)))
            bind.execute(sa.text(f"DELETE FROM golden_sqls WHERE id IN ({placeholders})"), {f"id_{i}": val for i, val in enumerate(duplicate_ids)})

    # Apply unique constraints using batch_alter_table for SQLite compatibility
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_projects_name', ['name'])

    with op.batch_alter_table('data_sources', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_datasources_project_name', ['project_id', 'name'])

    with op.batch_alter_table('schema_tables', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_schema_tables_ds_schema_table', ['data_source_id', 'table_schema', 'table_name'])

    with op.batch_alter_table('schema_columns', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_schema_columns_table_column', ['table_id', 'column_name'])

    with op.batch_alter_table('golden_sqls', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_golden_sqls_ds_question', ['data_source_id', 'question'])


def downgrade() -> None:
    """Downgrade schema (remove constraints)."""
    with op.batch_alter_table('golden_sqls', schema=None) as batch_op:
        batch_op.drop_constraint('uq_golden_sqls_ds_question', type_='unique')

    with op.batch_alter_table('schema_columns', schema=None) as batch_op:
        batch_op.drop_constraint('uq_schema_columns_table_column', type_='unique')

    with op.batch_alter_table('schema_tables', schema=None) as batch_op:
        batch_op.drop_constraint('uq_schema_tables_ds_schema_table', type_='unique')

    with op.batch_alter_table('data_sources', schema=None) as batch_op:
        batch_op.drop_constraint('uq_datasources_project_name', type_='unique')

    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_constraint('uq_projects_name', type_='unique')
