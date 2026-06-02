import type {
  AgentArtifact,
  AgentRunResponse,
  AgentWorkspaceContext,
  DataSource,
  Project,
  QueryResult,
  SchemaTable,
} from "../../lib/api";

interface SqlTabLike {
  id: string;
  title: string;
  type?: string;
  sqlDraft?: string;
}

interface BuildAgentWorkspaceContextArgs {
  currentProject?: Project | null;
  currentDatasource?: DataSource | null;
  activeSql?: string | null;
  selectedSql?: string | null;
  lastQueryResult?: QueryResult | Record<string, unknown> | null;
  lastError?: string | null;
  selectedTable?: SchemaTable | string | null;
  selectedColumns?: string[] | null;
  selectedArtifact?: AgentArtifact | null;
  recentAgentRun?: AgentRunResponse | null;
  openSqlTabs?: SqlTabLike[];
  editorAnnotations?: Array<Record<string, unknown>>;
}

export function buildAgentWorkspaceContext({
  currentProject,
  currentDatasource,
  activeSql,
  selectedSql,
  lastQueryResult,
  lastError,
  selectedTable,
  selectedColumns,
  selectedArtifact,
  recentAgentRun,
  openSqlTabs,
  editorAnnotations,
}: BuildAgentWorkspaceContextArgs): AgentWorkspaceContext | null {
  if (!currentDatasource?.id) return null;
  const tableName = typeof selectedTable === "string" ? selectedTable : selectedTable?.table_name;
  const annotations = editorAnnotations ?? extractEditorAnnotations(activeSql || "");
  return {
    project_id: currentProject?.id ?? currentDatasource.project_id ?? null,
    datasource_id: currentDatasource.id,
    active_sql: compactText(activeSql),
    selected_sql: compactText(selectedSql),
    last_query_result_preview: previewResult(lastQueryResult),
    last_error: compactText(lastError, 1200),
    selected_table_ids: typeof selectedTable === "object" && selectedTable?.id ? [selectedTable.id] : [],
    selected_table_names: tableName ? [tableName] : [],
    selected_column_refs: selectedColumns ?? [],
    selected_artifact_id: selectedArtifact?.id ?? null,
    recent_agent_run_id: recentAgentRun?.run_id ?? null,
    open_sql_tabs: (openSqlTabs || [])
      .filter((tab) => tab.type === "query" || tab.sqlDraft)
      .slice(0, 12)
      .map((tab) => ({
        id: tab.id,
        title: tab.title,
        sql: compactText(tab.sqlDraft, 1200),
      })),
    editor_annotations: annotations,
    semantic_context: {},
  };
}

export function extractEditorAnnotations(sql: string): Array<Record<string, unknown>> {
  return sql
    .split(/\r?\n/)
    .map((line, index) => ({ line: index + 1, text: line.trim() }))
    .filter((item) => item.text.startsWith("@"));
}

function previewResult(result?: QueryResult | Record<string, unknown> | null): Record<string, unknown> | null {
  if (!result) return null;
  const columns = Array.isArray(result.columns) ? result.columns.map(String) : [];
  const rows = Array.isArray(result.rows)
    ? (result.rows.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === "object") as Array<Record<string, unknown>>)
    : [];
  return {
    success: "success" in result ? result.success : undefined,
    columns,
    rows: rows.slice(0, 20),
    rowCount: "rowCount" in result ? result.rowCount : rows.length,
    latencyMs: "latencyMs" in result ? result.latencyMs : undefined,
    warnings: Array.isArray(result.warnings) ? result.warnings.map(String) : [],
    truncated: rows.length > 20 || Boolean("truncated" in result ? result.truncated : false),
  };
}

function compactText(value?: string | null, maxLength = 6000): string | null {
  const text = (value || "").trim();
  if (!text) return null;
  return text.length <= maxLength ? text : `${text.slice(0, maxLength - 3).trimEnd()}...`;
}
