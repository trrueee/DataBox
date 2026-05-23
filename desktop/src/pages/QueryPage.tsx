import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Check,
  CircleDot,
  Copy,
  Download,
  History,
  PencilLine,
  Play,
  Plus,
  ShieldAlert,
  Table,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import type { DataSource, GuardrailCheckResult, QueryHistory, QueryResult } from "../lib/api";
import { SqlEditor } from "../components/SqlEditor";
import { ChartPanel } from "../components/ChartPanel";
import { DataTable } from "../components/DataTable";
import { AiQueryInput } from "../components/AiQueryInput";
import { StatusIndicator } from "../components/StatusIndicator";

interface QueryPageProps {
  datasource: DataSource;
}

type ViewTab = "results" | "history";
type ResultViewMode = "table" | "chart";

type QueryTabState = {
  id: string;
  title: string;
  sql: string;
  savedSql: string;
  queryResult: QueryResult | null;
  queryError: string | null;
  guardrail: GuardrailCheckResult | null;
};

const defaultSql = "SELECT * FROM your_table LIMIT 100;";

function createQueryTab(index: number): QueryTabState {
  return {
    id: `qt-${index}-${Date.now()}`,
    title: `Query ${index}`,
    sql: defaultSql,
    savedSql: defaultSql,
    queryResult: null,
    queryError: null,
    guardrail: null,
  };
}

export const QueryPage = ({ datasource }: QueryPageProps) => {
  const [tabs, setTabs] = useState<QueryTabState[]>([]);
  const [activeEditorTabId, setActiveEditorTabId] = useState("");
  const [activeBottomTab, setActiveBottomTab] = useState<ViewTab>("results");
  const [resultViewMode, setResultViewMode] = useState<ResultViewMode>("table");
  const [queryLoading, setQueryLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [history, setHistory] = useState<QueryHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [renamingTabId, setRenamingTabId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [aiQuestion, setAiQuestion] = useState("");
  const [aiGenerating, setAiGenerating] = useState(false);
  const [showAiConfig, setShowAiConfig] = useState(false);
  const [aiConfig, setAiConfig] = useState({
    apiKey: "",
    apiBase: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
  });

  useEffect(() => {
    const initialTab = createQueryTab(1);
    setTabs([initialTab]);
    setActiveEditorTabId(initialTab.id);
    setActiveBottomTab("results");
    setRenamingTabId(null);
    setRenameDraft("");
    void fetchHistory();
  }, [datasource.id]);

  const activeEditorTab = useMemo(
    () => tabs.find((t) => t.id === activeEditorTabId) ?? tabs[0] ?? null,
    [activeEditorTabId, tabs],
  );

  const isDirty = (tab: QueryTabState) => tab.sql !== tab.savedSql;

  const fetchHistory = async () => {
    try {
      setHistoryLoading(true);
      setHistory(await api.listHistory(datasource.id));
    } finally {
      setHistoryLoading(false);
    }
  };

  const updateTabById = (tabId: string, updater: (tab: QueryTabState) => QueryTabState) => {
    setTabs((c) => c.map((t) => (t.id === tabId ? updater(t) : t)));
  };

  const updateActiveTab = (updater: (tab: QueryTabState) => QueryTabState) => {
    if (!activeEditorTab) return;
    updateTabById(activeEditorTab.id, updater);
  };

  const handleAddTab = () => {
    const next = createQueryTab(tabs.length + 1);
    setTabs((c) => [...c, next]);
    setActiveEditorTabId(next.id);
    setRenamingTabId(null);
  };

  const startRenaming = (tab: QueryTabState) => {
    setRenamingTabId(tab.id);
    setRenameDraft(tab.title);
  };

  const commitRename = () => {
    if (!renamingTabId) return;
    const nextTitle = renameDraft.trim();
    updateTabById(renamingTabId, (t) => ({ ...t, title: nextTitle || t.title }));
    setRenamingTabId(null);
    setRenameDraft("");
  };

  const handleCloseTab = (id: string) => {
    if (tabs.length === 1) return;
    const tab = tabs.find((t) => t.id === id);
    if (!tab) return;
    if (isDirty(tab) && !window.confirm(`"${tab.title}" 还有未执行的修改，确认关闭吗？`)) return;

    const index = tabs.findIndex((t) => t.id === id);
    const nextTabs = tabs.filter((t) => t.id !== id);
    setTabs(nextTabs);
    if (activeEditorTabId === id) {
      setActiveEditorTabId(nextTabs[Math.max(0, index - 1)]?.id ?? nextTabs[0].id);
    }
    if (renamingTabId === id) {
      setRenamingTabId(null);
      setRenameDraft("");
    }
  };

  const handleCopySql = async () => {
    if (!activeEditorTab) return;
    await navigator.clipboard.writeText(activeEditorTab.sql);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  const handleValidateSql = async () => {
    if (!activeEditorTab?.sql.trim()) return;
    try {
      setValidating(true);
      const guardrail = await api.validateSql(activeEditorTab.sql);
      updateActiveTab((t) => ({ ...t, guardrail, queryError: null }));
    } catch (error: any) {
      updateActiveTab((t) => ({ ...t, queryError: error.message ?? "SQL 校验失败" }));
    } finally {
      setValidating(false);
    }
  };

  const handleExecuteSql = async () => {
    if (!activeEditorTab?.sql.trim()) return;
    try {
      setQueryLoading(true);
      updateActiveTab((t) => ({ ...t, queryError: null, queryResult: null }));

      const checked = await api.validateSql(activeEditorTab.sql);
      updateActiveTab((t) => ({ ...t, guardrail: checked }));

      if (checked.result === "reject") {
        updateActiveTab((t) => ({ ...t, queryError: checked.message }));
        return;
      }

      const result = await api.executeSql(datasource.id, activeEditorTab.sql);
      updateActiveTab((t) => ({
        ...t,
        queryResult: result,
        queryError: null,
        guardrail: checked,
        savedSql: t.sql,
      }));
      setActiveBottomTab("results");
      await fetchHistory();
    } catch (error: any) {
      updateActiveTab((t) => ({ ...t, queryError: error.message ?? "SQL 执行失败" }));
    } finally {
      setQueryLoading(false);
    }
  };

  const handleExportCsv = () => {
    if (!activeEditorTab?.queryResult) return;
    const { columns, rows } = activeEditorTab.queryResult;
    const escapeCsv = (val: unknown): string => {
      if (val === null) return "";
      const s = String(val);
      if (s.includes(",") || s.includes('"') || s.includes("\n")) return `"${s.replace(/"/g, '""')}"`;
      return s;
    };
    const header = columns.map(escapeCsv).join(",");
    const body = rows.map((row) => columns.map((c) => escapeCsv(row[c])).join(",")).join("\n");
    const csv = "﻿" + header + "\n" + body;
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `databox_export_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleAiGenerate = async () => {
    const question = aiQuestion.trim();
    if (!question) return;
    try {
      setAiGenerating(true);
      updateActiveTab((t) => ({ ...t, queryError: null, queryResult: null }));
      const result = await api.generateSql(datasource.id, question, {
        apiKey: aiConfig.apiKey || undefined,
        apiBase: aiConfig.apiBase || undefined,
        model: aiConfig.model || undefined,
      });
      updateActiveTab((t) => ({ ...t, sql: result.sql, guardrail: result.guardrail, queryResult: null }));
      if (result.guardrail.result === "reject") {
        updateActiveTab((t) => ({ ...t, queryError: result.guardrail.message }));
      }
      setAiQuestion("");
    } catch (error: any) {
      updateActiveTab((t) => ({ ...t, queryError: error.message ?? "AI 生成 SQL 失败" }));
    } finally {
      setAiGenerating(false);
    }
  };

  return (
    <div
      className="animate-fade-in"
      style={{ display: "flex", flexDirection: "column", gap: 14, height: "100%", overflow: "hidden" }}
    >
      {/* ── AI Query Input ── */}
      <AiQueryInput
        value={aiQuestion}
        onChange={setAiQuestion}
        onSubmit={() => void handleAiGenerate()}
        loading={aiGenerating}
        onToggleConfig={() => setShowAiConfig((v) => !v)}
      />

      {/* ── LLM Config ── */}
      {showAiConfig && (
        <div className="lab-card animate-slide-down" style={{ padding: "14px 18px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <div>
              <label className="field-label">API Key</label>
              <input
                className="input-field input-field-sm"
                type="password"
                placeholder="留空使用离线模式"
                value={aiConfig.apiKey}
                onChange={(e) => setAiConfig((c) => ({ ...c, apiKey: e.target.value }))}
              />
            </div>
            <div>
              <label className="field-label">API Base URL</label>
              <input
                className="input-field input-field-sm"
                placeholder="https://api.openai.com/v1"
                value={aiConfig.apiBase}
                onChange={(e) => setAiConfig((c) => ({ ...c, apiBase: e.target.value }))}
              />
            </div>
            <div>
              <label className="field-label">Model</label>
              <input
                className="input-field input-field-sm"
                placeholder="gpt-4o-mini"
                value={aiConfig.model}
                onChange={(e) => setAiConfig((c) => ({ ...c, model: e.target.value }))}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Main Content: Editor + Guardrail ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1.5fr minmax(280px, 0.85fr)", gap: 14, flex: 1, overflow: "hidden", minHeight: 0 }}>
        {/* Left: Editor + Results */}
        <div style={{ display: "grid", gridTemplateRows: "minmax(200px, 1fr) auto", gap: 14, overflow: "hidden" }}>
          {/* SQL Editor */}
          <div className="lab-card" style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
            {/* Tab bar */}
            <div style={{ borderBottom: "1px solid var(--border-light)", padding: "6px 10px 0", background: "var(--bg-secondary)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 4, overflowX: "auto", paddingBottom: 6 }}>
                {tabs.map((tab) => {
                  const dirty = isDirty(tab);
                  const isActive = tab.id === activeEditorTab?.id;
                  const isRenaming = renamingTabId === tab.id;
                  return (
                    <div
                      key={tab.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                        padding: "6px 10px",
                        borderRadius: "6px 6px 0 0",
                        border: "1px solid",
                        borderColor: isActive ? "var(--border-light)" : "transparent",
                        borderBottomColor: isActive ? "var(--bg-surface)" : "transparent",
                        background: isActive ? "var(--bg-surface)" : "transparent",
                        minWidth: "fit-content",
                      }}
                    >
                      <button
                        onClick={() => setActiveEditorTabId(tab.id)}
                        onDoubleClick={() => startRenaming(tab)}
                        style={{
                          border: "none",
                          background: "transparent",
                          color: isActive ? "var(--text-primary)" : "var(--text-muted)",
                          cursor: "pointer",
                          fontSize: "0.8rem",
                          fontWeight: isActive ? 600 : 500,
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        {dirty && <CircleDot size={10} style={{ color: "var(--accent-amber)" }} />}
                        {isRenaming ? (
                          <input
                            className="input-field input-field-sm"
                            value={renameDraft}
                            autoFocus
                            onChange={(e) => setRenameDraft(e.target.value)}
                            onBlur={commitRename}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") commitRename();
                              if (e.key === "Escape") { setRenamingTabId(null); setRenameDraft(""); }
                            }}
                            style={{ width: 100 }}
                          />
                        ) : (
                          <span>{tab.title}</span>
                        )}
                      </button>
                      {!isRenaming && (
                        <button onClick={() => startRenaming(tab)} className="btn-ghost" style={{ padding: 1 }}>
                          <PencilLine size={11} />
                        </button>
                      )}
                      {tabs.length > 1 && (
                        <button onClick={() => handleCloseTab(tab.id)} className="btn-ghost" style={{ padding: 1 }}>
                          <X size={12} />
                        </button>
                      )}
                    </div>
                  );
                })}
                <button className="btn-ghost" onClick={handleAddTab} style={{ padding: "4px 8px", flexShrink: 0 }}>
                  <Plus size={13} />
                </button>
              </div>
            </div>

            {/* Toolbar */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "8px 14px",
                borderBottom: "1px solid var(--border-light)",
                gap: 8,
                flexWrap: "wrap",
              }}
            >
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                <span className="text-mono" style={{ fontWeight: 500, color: "var(--text-secondary)" }}>
                  {datasource.database_name}
                </span>
                {activeEditorTab && isDirty(activeEditorTab) && (
                  <span style={{ marginLeft: 8, color: "var(--accent-amber)" }}>· 未执行</span>
                )}
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button className="btn-ghost" onClick={handleCopySql}>
                  {copied ? <Check size={13} /> : <Copy size={13} />}
                  {copied ? "已复制" : "复制"}
                </button>
                <button
                  className="btn-secondary"
                  style={{ padding: "5px 10px", fontSize: "0.8rem" }}
                  onClick={handleValidateSql}
                  disabled={validating || !activeEditorTab}
                >
                  <ShieldAlert size={13} />
                  校验
                </button>
                <button
                  className="btn-primary"
                  style={{ padding: "5px 14px", fontSize: "0.82rem" }}
                  onClick={handleExecuteSql}
                  disabled={queryLoading || !activeEditorTab}
                >
                  <Play size={13} />
                  {queryLoading ? "执行中..." : "执行"}
                </button>
              </div>
            </div>

            {/* Editor */}
            <div style={{ flex: 1, minHeight: 0 }}>
              <SqlEditor
                value={activeEditorTab?.sql ?? ""}
                onChange={(v) => updateActiveTab((t) => ({ ...t, sql: v }))}
              />
            </div>
          </div>

          {/* Results / History */}
          <div className="lab-card" style={{ display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 180 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "8px 14px",
                borderBottom: "1px solid var(--border-light)",
                background: "var(--bg-secondary)",
              }}
            >
              <div className="pill-tabs">
                <button
                  className={`pill-tab ${activeBottomTab === "results" ? "active" : ""}`}
                  onClick={() => setActiveBottomTab("results")}
                >
                  <Table size={13} />
                  结果
                </button>
                <button
                  className={`pill-tab ${activeBottomTab === "history" ? "active" : ""}`}
                  onClick={() => setActiveBottomTab("history")}
                >
                  <History size={13} />
                  历史
                </button>
              </div>
              {activeEditorTab?.queryError && (
                <span className="status-badge status-badge-error" style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {activeEditorTab.queryError}
                </span>
              )}
            </div>

            <div style={{ flex: 1, overflow: "auto" }}>
              {activeBottomTab === "results" && (
                <>
                  {!activeEditorTab?.queryResult ? (
                    <div className="empty-state" style={{ padding: 36 }}>
                      <div className="empty-state-desc">执行安全 SQL 后，这里会展示查询结果</div>
                    </div>
                  ) : (
                    <div>
                      {/* Result meta bar */}
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "6px 16px",
                          borderBottom: "1px solid var(--border-light)",
                          fontSize: "0.78rem",
                          color: "var(--text-secondary)",
                        }}
                      >
                        <div style={{ display: "flex", gap: 16 }}>
                          <span>行数: <strong style={{ color: "var(--text-primary)" }}>{activeEditorTab.queryResult.rowCount}</strong></span>
                          <span>列数: <strong style={{ color: "var(--text-primary)" }}>{activeEditorTab.queryResult.columns.length}</strong></span>
                          <span>耗时: <strong style={{ color: "var(--text-primary)" }}>{activeEditorTab.queryResult.latencyMs}ms</strong></span>
                        </div>
                        <div style={{ display: "flex", gap: 4 }}>
                          <button
                            className={resultViewMode === "table" ? "btn-primary" : "btn-secondary"}
                            style={{ padding: "3px 8px", fontSize: "0.74rem" }}
                            onClick={() => setResultViewMode("table")}
                          >
                            <Table size={12} /> 表格
                          </button>
                          <button
                            className={resultViewMode === "chart" ? "btn-primary" : "btn-secondary"}
                            style={{ padding: "3px 8px", fontSize: "0.74rem" }}
                            onClick={() => setResultViewMode("chart")}
                          >
                            <BarChart3 size={12} /> 图表
                          </button>
                          <button
                            className="btn-ghost"
                            style={{ fontSize: "0.74rem" }}
                            onClick={handleExportCsv}
                          >
                            <Download size={12} /> CSV
                          </button>
                        </div>
                      </div>

                      {resultViewMode === "table" ? (
                        <DataTable
                          columns={activeEditorTab.queryResult.columns}
                          rows={activeEditorTab.queryResult.rows}
                          maxHeight="360px"
                        />
                      ) : (
                        <div style={{ padding: 12 }}>
                          <ChartPanel
                            columns={activeEditorTab.queryResult.columns}
                            rows={activeEditorTab.queryResult.rows}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}

              {activeBottomTab === "history" && (
                <>
                  {historyLoading ? (
                    <div style={{ padding: 24 }}>
                      {[1, 2, 3].map((i) => (
                        <div key={i} className="skeleton" style={{ height: 40, marginBottom: 6, borderRadius: 4 }} />
                      ))}
                    </div>
                  ) : history.length === 0 ? (
                    <div className="empty-state" style={{ padding: 36 }}>
                      <div className="empty-state-desc">还没有执行历史，执行一条 SQL 试试</div>
                    </div>
                  ) : (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>时间</th>
                          <th>SQL</th>
                          <th>审核</th>
                          <th>状态</th>
                          <th>行数</th>
                          <th>耗时</th>
                        </tr>
                      </thead>
                      <tbody>
                        {history.map((item) => (
                          <tr key={item.id}>
                            <td style={{ whiteSpace: "nowrap", fontSize: "0.8rem" }}>
                              {new Date(item.created_at).toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                            </td>
                            <td className="text-mono" style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: "0.78rem" }}>
                              {item.executed_sql || item.safe_sql || item.submitted_sql}
                            </td>
                            <td>
                              <StatusIndicator
                                type={item.guardrail_result === "pass" ? "success" : item.guardrail_result === "warn" ? "warning" : "error"}
                                size="sm"
                              />
                            </td>
                            <td>
                              <span style={{ color: item.execution_status === "success" ? "var(--accent-green)" : "var(--accent-red)", fontSize: "0.8rem" }}>
                                {item.execution_status}
                              </span>
                            </td>
                            <td className="cell-number">{item.rows_returned}</td>
                            <td className="cell-number">{item.execution_time_ms}ms</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* Right: Guardrail Panel */}
        <div className="lab-card" style={{ padding: 18, overflow: "auto" }}>
          <h3
            style={{
              fontSize: "0.92rem",
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginBottom: 16,
            }}
          >
            <ShieldAlert size={16} style={{ color: "var(--accent-indigo)" }} />
            Guardrail 安全审核
          </h3>

          {!activeEditorTab?.guardrail ? (
            <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", lineHeight: 1.7 }}>
              <p>点击「校验」或「执行」按钮后，这里会展示安全审核结果。</p>
              <div className="divider-spaced" />
              <p style={{ fontSize: "0.78rem" }}>
                Guardrail 会检查：危险语句、系统库访问、危险函数、多语句、无 LIMIT 等。
              </p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {/* Result badge */}
              <div>
                <StatusIndicator
                  type={
                    activeEditorTab.guardrail.result === "pass" ? "success"
                      : activeEditorTab.guardrail.result === "warn" ? "warning"
                      : "error"
                  }
                  label={
                    activeEditorTab.guardrail.result === "pass" ? "通过"
                      : activeEditorTab.guardrail.result === "warn" ? "警告"
                      : "拒绝"
                  }
                />
              </div>

              <p style={{ fontSize: "0.84rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                {activeEditorTab.guardrail.message}
              </p>

              {/* Safe SQL */}
              <div>
                <div style={{ fontWeight: 600, fontSize: "0.8rem", marginBottom: 6, color: "var(--text-secondary)" }}>
                  安全 SQL
                </div>
                <pre
                  style={{
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    background: "var(--bg-secondary)",
                    padding: 12,
                    borderRadius: 6,
                    fontSize: "0.8rem",
                    fontFamily: "var(--font-mono)",
                    color: "var(--text-primary)",
                    border: "1px solid var(--border-light)",
                    lineHeight: 1.6,
                  }}
                >
                  {activeEditorTab.guardrail.safeSql || "-"}
                </pre>
              </div>

              {/* Checks */}
              {activeEditorTab.guardrail.checks.length > 0 && (
                <div>
                  <div style={{ fontWeight: 600, fontSize: "0.8rem", marginBottom: 8, color: "var(--text-secondary)" }}>
                    检查项 ({activeEditorTab.guardrail.checks.length})
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {activeEditorTab.guardrail.checks.map((item, i) => (
                      <div
                        key={`${item.rule}-${i}`}
                        className="lab-card-accent"
                        style={{
                          padding: "8px 12px",
                          borderLeftColor: item.level === "reject" ? "var(--accent-red)" : "var(--accent-amber)",
                          background: item.level === "reject" ? "var(--accent-red-light)" : "var(--accent-amber-light)",
                          fontSize: "0.78rem",
                        }}
                      >
                        <span style={{ fontWeight: 600, fontFamily: "var(--font-mono)", fontSize: "0.72rem" }}>
                          {item.rule}
                        </span>
                        <span style={{ marginLeft: 6, color: "var(--text-secondary)" }}>{item.message}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
