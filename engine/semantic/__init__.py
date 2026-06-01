"""Lightweight semantic layer for local schema-aware Text-to-SQL."""

from engine.semantic.alias import AliasMatch, SemanticAliasResolver
from engine.semantic.query_plan import QueryDimension, QueryFilter, QueryJoin, QueryMetric, QueryPlan, QueryPlanBuilder
from engine.semantic.schema_linker import ColumnLink, SchemaLinker, SchemaLinkingResult, TableLink
from engine.semantic.semantic_context import SchemaContextBuilder

__all__ = [
    "AliasMatch",
    "SemanticAliasResolver",
    "QueryDimension",
    "QueryFilter",
    "QueryJoin",
    "QueryMetric",
    "QueryPlan",
    "QueryPlanBuilder",
    "ColumnLink",
    "SchemaLinker",
    "SchemaLinkingResult",
    "SchemaContextBuilder",
    "TableLink",
]
