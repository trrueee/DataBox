from __future__ import annotations

from sqlalchemy.orm import Session

from engine.models import SchemaColumn, SchemaTable
from engine.semantic.schema_linker import SchemaLinkingResult


class SchemaContextBuilder:
    """Render linked schema metadata into the CREATE TABLE style prompt context."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, result: SchemaLinkingResult) -> str:
        tables = [link.table for link in result.tables]
        if not tables:
            return "No schema metadata found. Please sync the data source first."
        return self.build_for_tables(tables)

    def build_for_tables(self, tables: list[SchemaTable]) -> str:
        if not tables:
            return "No schema metadata found. Please sync the data source first."

        context_lines: list[str] = []
        for table in tables:
            table_comment = str(table.table_comment or "").strip()
            comment_suffix = f" -- {table_comment}" if table_comment else ""
            context_lines.append(f"CREATE TABLE {table.table_name} ({comment_suffix}")

            columns = sorted(table.columns, key=lambda column: (column.ordinal_position or 0, str(column.column_name)))
            for index, column in enumerate(columns):
                line = self._render_column(column)
                if index < len(columns) - 1:
                    line += ","
                context_lines.append(line)

            context_lines.append(");\n")

        return "\n".join(context_lines)

    def _render_column(self, column: SchemaColumn) -> str:
        parts = [f"  {column.column_name}", str(column.column_type or column.data_type or "TEXT")]
        if column.is_primary_key:
            parts.append("PRIMARY KEY")
        if not bool(column.is_nullable):
            parts.append("NOT NULL")

        fk_ref = self._foreign_key_reference(column)
        if fk_ref:
            parts.append(fk_ref)

        comment = str(column.column_comment or "").strip()
        if comment:
            escaped_comment = comment.replace("'", "''")
            parts.append(f"COMMENT '{escaped_comment}'")

        return " ".join(parts)

    def _foreign_key_reference(self, column: SchemaColumn) -> str:
        if not column.is_foreign_key or not column.foreign_table_id:
            return ""

        target_table = self.db.query(SchemaTable).filter(SchemaTable.id == column.foreign_table_id).first()
        if not target_table:
            return ""

        target_column_name = "id"
        if column.foreign_column_id:
            target_column = self.db.query(SchemaColumn).filter(SchemaColumn.id == column.foreign_column_id).first()
            if target_column:
                target_column_name = str(target_column.column_name)

        return f"REFERENCES {target_table.table_name}({target_column_name})"
