// Force Vite Hot-Reload to clear stale parser cache
import { lazy, Suspense, useState, useMemo, useEffect, useCallback } from "react";
import {
  Database,
  Table2,
  Terminal,
  ChevronDown,
  ChevronRight,
  Plus,
  X,
  Eye,
  Sparkles,
  ShieldCheck,
  Keyboard,
  Play,
  Search,
  RefreshCw,
  Code2,
  HardDrive,
  Settings,
  MoreHorizontal
} from "lucide-react";
import { api } from "../lib/api";
import type { DataSource, Project, SchemaTable } from "../lib/api";
import { EnvironmentsPage } from "./EnvironmentsPage";
import { BackupsPage } from "./BackupsPage";
import { DataSourcesPage } from "./DataSourcesPage";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { PromptDialog } from "../components/PromptDialog";

// Tab structure for the workspace
export interface WorkbenchTab {
  id: string; // e.g. "query_123" or "table:users"
  type: "query" | "table" | "er" | "datasources" | "history" | "diagnostics";
  title: string;
  dirty?: boolean;
  closable?: boolean;
  connectionId?: string;
  databaseName?: string;
  tableName?: string;
  activeSubTab?: "data" | "schema" | "er" | "design";
  sqlDraft?: string;
  resultState?: "idle" | "running" | "success" | "error" | "timeout" | "cancelled";
  lastExecutedAt?: number;
  actionTrigger?: {
    type: "execute" | "stop" | "validate" | "export" | "format";
    nonce: number;
  };
}

interface WorkbenchPageProps {
  // Connections and metadata states
  projects: Project[];
  activeProject: Project | null;
  setActiveProject: (p: Project | null) => void;
  datasources: DataSource[];
  activeDataSource: DataSource | null;
  setActiveDataSource: (ds: DataSource | null) => void;
  schemaTables: SchemaTable[];
  loadingObjects: boolean;
  loadingTree: boolean;
  onRefreshSchemaTables: (datasourceId: string) => Promise<void>;
  onRefreshDatasources: () => Promise<void>;
  onCreateProject: (name: string) => Promise<void>;
}

type QueryTabStatePatch = Pick<WorkbenchTab, "resultState" | "sqlDraft" | "dirty">;

const DashboardPage = lazy(() =>
  import("./DashboardPage").then((module) => ({ default: module.DashboardPage })),
);
const QueryPage = lazy(() =>
  import("./QueryPage").then((module) => ({ default: module.QueryPage })),
);
const SchemaPage = lazy(() =>
  import("./SchemaPage").then((module) => ({ default: module.SchemaPage })),
);
const DataPage = lazy(() =>
  import("./DataPage").then((module) => ({ default: module.DataPage })),
);

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

// PREFIX GROUPS FOR TREE OBJECTS
const MODULE_PREFIXES: [string, string][] = [
  ["account_", "账号模块"],
  ["ai_", "AI 智能模块"],
  ["agent_", "任务模块"],
  ["auto_", "任务模块"],
  ["billing_", "计费模块"],
  ["content_", "内容模块"],
  ["id_", "身份组织模块"],
  ["login_", "认证会话模块"],
  ["media_", "媒体素材模块"],
  ["monitoring_", "监控模块"],
  ["nurture_", "客户培育模块"],
  ["notification_", "通知模块"],
  ["platform_", "平台账号模块"],
  ["publish_", "发布模块"],
  ["rbac_", "权限模块"],
  ["sales_", "销售模块"],
  ["token_", "Token 账户模块"],
  ["user_", "用户模块"],
  ["video_", "视频模块"],
  ["xhs_", "小红书模块"],
  ["audit_", "审计模块"],
  ["scheduler_", "调度模块"],
];

const MODULE_ORDER = [
  "账号模块",
  "身份组织模块",
  "认证会话模块",
  "平台账号模块",
  "Token 账户模块",
  "销售模块",
  "发布模块",
  "媒体素材模块",
  "视频模块",
  "小红书模块",
  "客户培育模块",
  "AI 智能模块",
  "任务模块",
  "计费模块",
  "审计模块",
  "权限模块",
  "监控模块",
  "通知模块",
  "用户模块",
  "内容模块",
  "调度模块",
  "通用模块",
];

function getModuleTag(tableName: string): string {
  for (const [prefix, tag] of MODULE_PREFIXES) {
    if (tableName.startsWith(prefix)) return tag;
  }
  return "通用模块";
}

export const WorkbenchPage = ({
  projects,
  activeProject,
  setActiveProject,
  datasources,
  activeDataSource,
  setActiveDataSource,
  schemaTables,
  loadingObjects,
  loadingTree,
  onRefreshSchemaTables,
  onRefreshDatasources,
  onCreateProject,
}: WorkbenchPageProps) => {
  // compact overlay modal states
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showBackupsModal, setShowBackupsModal] = useState(false);
  const [showEnvironmentsModal, setShowEnvironmentsModal] = useState(false);
  const [showDashboardModal, setShowDashboardModal] = useState(false);
  const [showCreateProject, setShowCreateProject] = useState(false);
  const [showMoreMenu, setShowMoreMenu] = useState(false);

  // Tabs management
  const [tabs, setTabs] = useState<WorkbenchTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);

  // Object Explorer Tree expansion states
  const [treeSearch, setTreeSearch] = useState("");
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const [tablesFolderExpanded, setTablesFolderExpanded] = useState(true);
  const [viewsFolderExpanded, setViewsFolderExpanded] = useState(false);
  const [funcsFolderExpanded, setFuncsFolderExpanded] = useState(false);
  const [procsFolderExpanded, setProcsFolderExpanded] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Floating Contextual AI Panel
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiResponse, setAiResponse] = useState("");
  const [aiLoading, setAiLoading] = useState(false);

  // Open active tab
  const activeTab = useMemo(() => {
    return tabs.find(t => t.id === activeTabId) || null;
  }, [tabs, activeTabId]);

  const handleActiveQueryStateChange = useCallback((state: QueryTabStatePatch) => {
    if (!activeTabId) return;
    setTabs((prev) =>
      prev.map((tab) => {
        if (tab.id !== activeTabId) return tab;
        const nextResultState = state.resultState ?? tab.resultState;
        const nextSqlDraft = state.sqlDraft ?? tab.sqlDraft;
        const nextDirty = state.dirty ?? tab.dirty;
        if (
          tab.resultState === nextResultState &&
          tab.sqlDraft === nextSqlDraft &&
          tab.dirty === nextDirty
        ) {
          return tab;
        }
        return {
          ...tab,
          resultState: nextResultState,
          sqlDraft: nextSqlDraft,
          dirty: nextDirty,
        };
      }),
    );
  }, [activeTabId]);

  // Synchronize focused tab's connection context with active sidebar connection
  const handleSelectTab = (tabId: string) => {
    setActiveTabId(tabId);
    const tab = tabs.find(t => t.id === tabId);
    if (tab && tab.connectionId && datasources) {
      const boundDs = datasources.find(d => d.id === tab.connectionId);
      if (boundDs && boundDs.id !== activeDataSource?.id) {
        setActiveDataSource(boundDs);
      }
    }
  };

  // Action Trigger Helper
  const triggerActiveTabAction = (actionType: "execute" | "stop" | "validate" | "export" | "format") => {
    if (!activeTabId) return;
    setTabs(prev => prev.map(t => t.id === activeTabId ? {
      ...t,
      actionTrigger: {
        type: actionType,
        nonce: Date.now()
      }
    } : t));
  };

  // Environment badge indicator styling
  const getEnvBadgeStyle = () => {
    if (!activeDataSource) return { bg: "rgba(148, 163, 184, 0.1)", color: "var(--text-muted)", label: "绂荤嚎" };
    if (activeDataSource.env === "prod") return { bg: "rgba(239, 68, 68, 0.12)", color: "var(--accent-red)", label: "PROD" };
    if (activeDataSource.env === "test") return { bg: "rgba(245, 158, 11, 0.12)", color: "var(--accent-amber)", label: "TEST" };
    return { bg: "rgba(16, 185, 129, 0.12)", color: "var(--accent-green)", label: "DEV" };
  };
  const envBadge = getEnvBadgeStyle();

  // Unified tables grouping algorithm
  const filteredTables = useMemo(() => {
    return schemaTables.filter(
      (t) =>
        t.table_name.toLowerCase().includes(treeSearch.toLowerCase()) ||
        t.table_comment.toLowerCase().includes(treeSearch.toLowerCase()),
    );
  }, [schemaTables, treeSearch]);

  const groupedTables = useMemo(() => {
    const groups = new Map<string, SchemaTable[]>();
    for (const t of filteredTables) {
      const tag = t.module_tag || getModuleTag(t.table_name);
      if (!groups.has(tag)) {
        groups.set(tag, []);
      }
      groups.get(tag)!.push(t);
    }
    return Array.from(groups.entries())
      .sort(([left], [right]) => {
        const leftIndex = MODULE_ORDER.indexOf(left);
        const rightIndex = MODULE_ORDER.indexOf(right);
        const normalizedLeft = leftIndex === -1 ? MODULE_ORDER.length : leftIndex;
        const normalizedRight = rightIndex === -1 ? MODULE_ORDER.length : rightIndex;
        return normalizedLeft - normalizedRight || left.localeCompare(right, "zh-Hans-CN");
      })
      .map(([tag, group]) => ({
        tag,
        tables: [...group].sort((a, b) => a.table_name.localeCompare(b.table_name)),
      }));
  }, [filteredTables]);

  // 鈹€鈹€ Tab Management Handlers 鈹€鈹€
  const handleOpenQueryTab = useCallback((sqlDraft?: string, title?: string) => {
    const id = `query:${Date.now()}`;
    const newTab: WorkbenchTab = {
      id,
      type: "query",
      title: title || `查询_${tabs.filter(t => t.type === "query").length + 1}`,
      sqlDraft: sqlDraft || "",
      connectionId: activeDataSource?.id,
      databaseName: activeDataSource?.database_name
    };
    setTabs(prev => [...prev, newTab]);
    setActiveTabId(id);
  }, [activeDataSource?.database_name, activeDataSource?.id, tabs]);

  // Global Keyboard Shortcut listeners
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "t") {
        e.preventDefault();
        handleOpenQueryTab();
      }
    };
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, [handleOpenQueryTab]);

  const handleOpenTableTab = (tableName: string, subTab: "data" | "schema" | "er" | "design" = "data") => {
    const id = `table:${tableName}`;
    const exists = tabs.some(t => t.id === id);
    if (exists) {
      setTabs(prev => prev.map(t => t.id === id ? { ...t, activeSubTab: subTab } : t));
      setActiveTabId(id);
    } else {
      const newTab: WorkbenchTab = {
        id,
        type: "table",
        title: `表: ${tableName}`,
        tableName,
        activeSubTab: subTab,
        connectionId: activeDataSource?.id,
        databaseName: activeDataSource?.database_name
      };
      setTabs(prev => [...prev, newTab]);
      setActiveTabId(id);
    }
  };

  const handleCloseTab = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const tab = tabs.find(t => t.id === id);
    if (tab && tab.dirty) {
      const confirmed = window.confirm(`"${tab.title}" 还有未执行或未保存的修改，确认关闭吗？`);
      if (!confirmed) return;
    }
    const nextTabs = tabs.filter(t => t.id !== id);
    setTabs(nextTabs);
    if (activeTabId === id) {
      setActiveTabId(nextTabs[nextTabs.length - 1]?.id || null);
    }
  };

  const handleSwitchSubTab = (tabId: string, subTab: "data" | "schema" | "er" | "design") => {
    setTabs(prev => prev.map(t => t.id === tabId ? { ...t, activeSubTab: subTab } : t));
  };

  // Quick SQL select generation
  const handleGenerateSelect = (tableName: string) => {
    const sql = `SELECT * FROM \`${tableName}\` LIMIT 100;`;
    handleOpenQueryTab(sql, `查询: ${tableName}`);
  };

  // Contextual AI prompts based on current tab
  const handleAiContextAction = async (promptText: string) => {
    if (!activeDataSource) return;
    setAiPanelOpen(true);
    setAiLoading(true);
    setAiResponse("");
    setAiPrompt(promptText);
    try {
      // Direct call to general AI SQL/Schema logic
      const prompt = `数据源: ${activeDataSource.name} (${activeDataSource.database_name})\n当前表: ${activeTab?.tableName || "无"}\n当前查询: ${promptText}\n请生成或解释 SQL 结构、优化方案或数据趋势。`;
      const res = await api.generateSql(activeDataSource.id, prompt);
      setAiResponse(res.sql || res.guardrail?.message || "AI 已完成回答。");
    } catch (err: unknown) {
      setAiResponse(`出错了: ${getErrorMessage(err, "AI request failed")}`);
    } finally {
      setAiLoading(false);
    }
  };

  const handleAskGeneralAi = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!aiPrompt.trim() || !activeDataSource) return;
    setAiLoading(true);
    setAiResponse("");
    try {
      const res = await api.generateSql(activeDataSource.id, aiPrompt);
      setAiResponse(res.sql || `生成 SQL:\n${res.sql}\n\n安全校验: ${res.guardrail?.message ?? "通过"}`);
    } catch (err: unknown) {
      setAiResponse(`生成失败: ${getErrorMessage(err, "AI request failed")}`);
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: sidebarCollapsed ? "0px minmax(0, 1fr)" : "250px minmax(0, 1fr)",
        height: "100%",
        width: "100%",
        overflow: "hidden",
        background: "var(--bg-primary)",
        transition: "grid-template-columns 0.22s cubic-bezier(0.4, 0, 0.2, 1)"
      }}
    >
      {/* 鈺愨晲鈺?LEFT OBJECT EXPLORER TREE 鈺愨晲鈺?*/}
      <aside
        style={{
          display: "flex",
          flexDirection: "column",
          background: "var(--bg-surface)",
          borderRight: sidebarCollapsed ? "none" : "1px solid var(--border-light)",
          overflow: "hidden",
          height: "100%",
        }}
      >
        <div style={{ width: 250, display: "flex", flexDirection: "column", height: "100%" }}>

          {/* Sidebar Header with Object Explorer Label */}
          <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--border-light)", background: "rgba(0,0,0,0.01)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: 6 }}>
              <Code2 size={13} style={{ color: "var(--accent-indigo)" }} />
              对象资源管理器
            </span>
            <button
              className="btn-ghost"
              onClick={() => setSidebarCollapsed(true)}
              style={{ padding: 2 }}
              title="闅愯棌渚ф爮"
            >
              <ChevronRight size={13} style={{ transform: "rotate(180deg)" }} />
            </button>
          </div>

          {/* Unified Tree View Scroll Area */}
          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", padding: "8px 10px" }}>
            {/* Project Connection Root */}
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {loadingTree ? (
                <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 6 }}>
                  <div className="skeleton" style={{ height: 20, borderRadius: 4 }} />
                  <div className="skeleton" style={{ height: 20, borderRadius: 4 }} />
                </div>
              ) : datasources.length === 0 ? (
                <div style={{ padding: "20px 10px", fontSize: "0.76rem", color: "var(--text-muted)", textAlign: "center" }}>
                  暂无连接，请先去 [数据源] 页面添加
                </div>
              ) : (
                datasources.map((ds) => {
                  const isConnected = activeDataSource?.id === ds.id;
                  return (
                    <div key={ds.id} style={{ display: "flex", flexDirection: "column" }}>
                      {/* Connection Root Node */}
                      <button
                        onClick={() => setActiveDataSource(ds)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          width: "100%",
                          padding: "6px 8px",
                          border: "none",
                          borderRadius: 6,
                          background: isConnected ? "var(--bg-active)" : "transparent",
                          color: isConnected ? "var(--accent-indigo)" : "var(--text-secondary)",
                          cursor: "pointer",
                          textAlign: "left",
                          transition: "background 0.15s",
                        }}
                      >
                        <ChevronRight
                          size={12}
                          style={{
                            transform: isConnected ? "rotate(90deg)" : "rotate(0deg)",
                            transition: "transform 0.15s",
                            opacity: 0.5
                          }}
                        />
                        <Database size={12} style={{ opacity: isConnected ? 1 : 0.6 }} />
                        <span style={{ fontSize: "0.78rem", fontWeight: isConnected ? 700 : 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {ds.name}
                        </span>
                      </button>

                      {/* Database & Children under Active Connection */}
                      {isConnected && (
                        <div style={{ paddingLeft: 16, marginTop: 2, display: "flex", flexDirection: "column", gap: 2 }}>
                          {/* Active Database Node */}
                          <div style={{ display: "flex", flexDirection: "column" }}>
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 6,
                                padding: "4px 8px",
                                color: "var(--text-primary)",
                                fontSize: "0.76rem",
                              }}
                            >
                              <ChevronDown size={11} style={{ opacity: 0.5 }} />
                              <HardDrive size={11} style={{ color: "var(--accent-indigo)" }} />
                              <span style={{ fontWeight: 600 }}>{ds.database_name}</span>
                            </div>

                            {/* Schema Folders */}
                            <div style={{ paddingLeft: 12, marginTop: 2, display: "flex", flexDirection: "column", gap: 1 }}>

                              {/* 1. Tables Folder */}
                              <div style={{ display: "flex", flexDirection: "column" }}>
                                <button
                                  onClick={() => setTablesFolderExpanded(!tablesFolderExpanded)}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 5,
                                    width: "100%",
                                    padding: "4px 8px",
                                    border: "none",
                                    background: "transparent",
                                    color: "var(--text-secondary)",
                                    fontSize: "0.76rem",
                                    cursor: "pointer",
                                    textAlign: "left",
                                  }}
                                >
                                  {tablesFolderExpanded ? <ChevronDown size={10} style={{ opacity: 0.5 }} /> : <ChevronRight size={10} style={{ opacity: 0.5 }} />}
                                  <Table2 size={11} style={{ color: "var(--accent-indigo)", opacity: 0.8 }} />
                                  <span style={{ fontWeight: 500 }}>表</span>
                                  <span style={{ color: "var(--text-muted)", fontSize: "0.68rem" }}>({schemaTables.length})</span>
                                </button>

                                {tablesFolderExpanded && (
                                  <div style={{ paddingLeft: 12, display: "flex", flexDirection: "column", gap: 2, marginTop: 4 }}>
                                    {/* Search tables input inside tree */}
                                    <div style={{ display: "flex", gap: 4, padding: "0 4px", marginBottom: 4 }}>
                                      <div style={{ position: "relative", flex: 1 }}>
                                        <Search size={10} style={{ position: "absolute", left: 6, top: 7, color: "var(--text-muted)" }} />
                                        <input
                                          className="input-field input-field-sm"
                                          placeholder="过滤数据表..."
                                          value={treeSearch}
                                          onChange={(e) => setTreeSearch(e.target.value)}
                                          style={{ height: 22, fontSize: "0.72rem", paddingLeft: 18 }}
                                        />
                                      </div>
                                      <button
                                        className="btn-ghost"
                                        onClick={() => void onRefreshSchemaTables(ds.id)}
                                        disabled={loadingObjects}
                                        style={{ padding: "2px 4px", border: "1px solid var(--border-light)", borderRadius: 4 }}
                                        title="刷新结构表"
                                      >
                                        <RefreshCw size={10} className={loadingObjects ? "animate-spin" : ""} />
                                      </button>
                                    </div>

                                    {/* Table Items */}
                                    {loadingObjects ? (
                                      <div style={{ display: "flex", flexDirection: "column", gap: 4, padding: "4px 8px" }}>
                                        <div className="skeleton" style={{ height: 18, borderRadius: 3 }} />
                                        <div className="skeleton" style={{ height: 18, borderRadius: 3 }} />
                                      </div>
                                    ) : filteredTables.length === 0 ? (
                                      <div style={{ padding: "8px", fontSize: "0.72rem", color: "var(--text-muted)", textAlign: "center" }}>
                                        没有匹配的表
                                      </div>
                                    ) : (
                                      <div style={{ display: "flex", flexDirection: "column", gap: 1, maxHeight: 380, overflowY: "auto" }}>
                                        {groupedTables.map(({ tag, tables }) => {
                                          const isCollapsed = collapsedGroups.has(tag);
                                          return (
                                            <div key={tag} style={{ margin: "1px 0" }}>
                                              <button
                                                onClick={() => {
                                                  setCollapsedGroups(prev => {
                                                    const next = new Set(prev);
                                                    if (next.has(tag)) next.delete(tag);
                                                    else next.add(tag);
                                                    return next;
                                                  });
                                                }}
                                                style={{
                                                  display: "flex",
                                                  alignItems: "center",
                                                  width: "100%",
                                                  gap: 4,
                                                  padding: "3px 6px",
                                                  border: "none",
                                                  background: "rgba(0,0,0,0.015)",
                                                  borderRadius: 4,
                                                  fontSize: "0.7rem",
                                                  fontWeight: 700,
                                                  color: "var(--text-secondary)",
                                                  cursor: "pointer",
                                                  textAlign: "left"
                                                }}
                                              >
                                                <span style={{ fontSize: "0.55rem", transition: "transform 0.15s", transform: isCollapsed ? "rotate(-90deg)" : "rotate(0deg)" }}>
                                                  ▾
                                                </span>
                                                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                                                  {tag}
                                                </span>
                                                <span style={{ color: "var(--text-muted)", fontSize: "0.65rem", fontWeight: 400 }}>
                                                  ({tables.length})
                                                </span>
                                              </button>

                                              {!isCollapsed && (
                                                <div style={{ display: "flex", flexDirection: "column", gap: 1, paddingLeft: 8, marginTop: 2 }}>
                                                  {tables.map((table) => {
                                                    const isTabActive = activeTab?.type === "table" && activeTab.tableName === table.table_name;
                                                    return (
                                                      <div
                                                        key={table.id}
                                                        style={{
                                                          display: "flex",
                                                          alignItems: "center",
                                                          borderRadius: 4,
                                                          background: isTabActive ? "var(--bg-active)" : "transparent",
                                                        }}
                                                        className="tree-item-row group"
                                                      >
                                                        <button
                                                          onClick={() => handleOpenTableTab(table.table_name, "schema")}
                                                          onDoubleClick={() => handleOpenTableTab(table.table_name, "data")}
                                                          style={{
                                                            flex: 1,
                                                            display: "flex",
                                                            alignItems: "center",
                                                            gap: 5,
                                                            padding: "4px 6px",
                                                            border: "none",
                                                            background: "transparent",
                                                            color: isTabActive ? "var(--accent-indigo)" : "var(--text-secondary)",
                                                            cursor: "pointer",
                                                            textAlign: "left",
                                                            minWidth: 0,
                                                          }}
                                                          title={`${table.table_name} (${table.table_comment || "无备注"})`}
                                                        >
                                                          <Table2 size={11} style={{ flexShrink: 0, opacity: isTabActive ? 1 : 0.4 }} />
                                                          <span style={{ fontSize: "0.74rem", fontWeight: isTabActive ? 600 : 400, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                                            {table.table_name}
                                                          </span>
                                                        </button>

                                                        <div style={{ display: "flex", alignItems: "center", gap: 2, paddingRight: 4 }}>
                                                          <button
                                                            onClick={() => handleAiContextAction(`分析并解释数据库表 \`${table.table_name}\` (${table.table_comment || "无备注"}) 的设计意图、字段规范与业务含义，并指出它的核心关联表。`)}
                                                            className="btn-ghost"
                                                            style={{ padding: 2 }}
                                                            title="AI 智能解释表结构"
                                                          >
                                                            <Sparkles size={10} style={{ color: "var(--accent-indigo)" }} />
                                                          </button>
                                                          <button
                                                            onClick={() => handleOpenTableTab(table.table_name, "data")}
                                                            className="btn-ghost"
                                                            style={{ padding: 2 }}
                                                            title="鐩存帴鐪嬫暟 (Data Mode)"
                                                          >
                                                            <Eye size={10} />
                                                          </button>
                                                          <button
                                                            onClick={() => handleGenerateSelect(table.table_name)}
                                                            className="btn-ghost"
                                                            style={{ padding: 2 }}
                                                            title="生成 SELECT SQL 查询"
                                                          >
                                                            <Terminal size={10} />
                                                          </button>
                                                        </div>
                                                      </div>
                                                    );
                                                  })}
                                                </div>
                                              )}
                                            </div>
                                          );
                                        })}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>

                              {/* 2. Views Folder */}
                              <div style={{ display: "flex", flexDirection: "column" }}>
                                <button
                                  onClick={() => setViewsFolderExpanded(!viewsFolderExpanded)}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 5,
                                    width: "100%",
                                    padding: "4px 8px",
                                    border: "none",
                                    background: "transparent",
                                    color: "var(--text-secondary)",
                                    fontSize: "0.76rem",
                                    cursor: "pointer",
                                    textAlign: "left",
                                  }}
                                >
                                  {viewsFolderExpanded ? <ChevronDown size={10} style={{ opacity: 0.5 }} /> : <ChevronRight size={10} style={{ opacity: 0.5 }} />}
                                  <Eye size={11} style={{ color: "var(--text-muted)", opacity: 0.7 }} />
                                  <span style={{ fontWeight: 500 }}>视图</span>
                                  <span style={{ color: "var(--text-muted)", fontSize: "0.68rem" }}>(0)</span>
                                </button>
                                {viewsFolderExpanded && (
                                  <div style={{ padding: "4px 24px", fontSize: "0.72rem", color: "var(--text-muted)" }}>
                                    暂无视图
                                  </div>
                                )}
                              </div>

                              {/* 3. Functions Folder */}
                              <div style={{ display: "flex", flexDirection: "column" }}>
                                <button
                                  onClick={() => setFuncsFolderExpanded(!funcsFolderExpanded)}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 5,
                                    width: "100%",
                                    padding: "4px 8px",
                                    border: "none",
                                    background: "transparent",
                                    color: "var(--text-secondary)",
                                    fontSize: "0.76rem",
                                    cursor: "pointer",
                                    textAlign: "left",
                                  }}
                                >
                                  {funcsFolderExpanded ? <ChevronDown size={10} style={{ opacity: 0.5 }} /> : <ChevronRight size={10} style={{ opacity: 0.5 }} />}
                                  <Code2 size={11} style={{ color: "var(--text-muted)", opacity: 0.7 }} />
                                  <span style={{ fontWeight: 500 }}>鍑芥暟</span>
                                  <span style={{ color: "var(--text-muted)", fontSize: "0.68rem" }}>(0)</span>
                                </button>
                                {funcsFolderExpanded && (
                                  <div style={{ padding: "4px 24px", fontSize: "0.72rem", color: "var(--text-muted)" }}>
                                    鏆傛棤鍑芥暟
                                  </div>
                                )}
                              </div>

                              {/* 4. Procedures Folder */}
                              <div style={{ display: "flex", flexDirection: "column" }}>
                                <button
                                  onClick={() => setProcsFolderExpanded(!procsFolderExpanded)}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 5,
                                    width: "100%",
                                    padding: "4px 8px",
                                    border: "none",
                                    background: "transparent",
                                    color: "var(--text-secondary)",
                                    fontSize: "0.76rem",
                                    cursor: "pointer",
                                    textAlign: "left",
                                  }}
                                >
                                  {procsFolderExpanded ? <ChevronDown size={10} style={{ opacity: 0.5 }} /> : <ChevronRight size={10} style={{ opacity: 0.5 }} />}
                                  <Terminal size={11} style={{ color: "var(--text-muted)", opacity: 0.7 }} />
                                  <span style={{ fontWeight: 500 }}>瀛樺偍杩囩▼</span>
                                  <span style={{ color: "var(--text-muted)", fontSize: "0.68rem" }}>(0)</span>
                                </button>
                                {procsFolderExpanded && (
                                  <div style={{ padding: "4px 24px", fontSize: "0.72rem", color: "var(--text-muted)" }}>
                                    鏆傛棤瀛樺偍杩囩▼
                                  </div>
                                )}
                              </div>

                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </aside>

      {/* 鈺愨晲鈺?RIGHT WORKSPACE GRID 鈺愨晲鈺?*/}
      <section
        style={{
          display: "flex",
          flexDirection: "column",
          height: "100%",
          width: "100%",
          overflow: "hidden",
          position: "relative"
        }}
      >

            {/* 鈹€鈹€ Layer 1: Global High-Density Header (36px) 鈹€鈹€ */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                background: "var(--bg-surface)",
                borderBottom: "1px solid var(--border-light)",
                padding: "0 12px",
                height: 36,
                flexShrink: 0,
                userSelect: "none"
              }}
            >
              {/* Left section: Logo | Project Selector | Active Connection Dropdown */}
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: "0.8rem", fontWeight: 800, color: "var(--accent-indigo)", letterSpacing: "-0.01em", display: "flex", alignItems: "center", gap: 4 }}>
                  <HardDrive size={13} style={{ color: "var(--accent-indigo)" }} />
                  DataBox
                </span>

                <div style={{ width: 1, height: 12, background: "var(--border-light)" }} />

                {/* Project Selector with Quick Plus */}
                <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
                  <span style={{ fontSize: "0.74rem", color: "var(--text-muted)", userSelect: "none" }}>馃搧</span>
                  <select
                    value={activeProject?.id || ""}
                    onChange={(e) => {
                      const selected = projects.find(p => p.id === e.target.value);
                      if (selected) setActiveProject(selected);
                    }}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "var(--text-secondary)",
                      fontSize: "0.76rem",
                      fontWeight: 600,
                      cursor: "pointer",
                      paddingRight: 2,
                      outline: "none",
                      fontFamily: "inherit"
                    }}
                  >
                    {projects.map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => setShowCreateProject(true)}
                    className="btn-ghost"
                    style={{ padding: "1px 2px", color: "var(--text-muted)", display: "flex", alignItems: "center" }}
                    title="创建新项目"
                  >
                    <Plus size={11} />
                  </button>
                </div>

                <div style={{ width: 1, height: 12, background: "var(--border-light)" }} />

                {/* Connection Selector */}
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ fontSize: "0.74rem", color: envBadge.color }}>●</span>
                  <select
                    value={activeDataSource?.id || ""}
                    onChange={(e) => {
                      const selected = datasources.find(d => d.id === e.target.value);
                      if (selected) setActiveDataSource(selected);
                    }}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "var(--text-primary)",
                      fontSize: "0.76rem",
                      fontWeight: 700,
                      cursor: "pointer",
                      paddingRight: 2,
                      outline: "none",
                      fontFamily: "inherit",
                      maxWidth: 160
                    }}
                  >
                    {datasources.length === 0 ? (
                      <option value="">(无激活连接)</option>
                    ) : (
                      datasources.map(d => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))
                    )}
                  </select>

                  {activeDataSource && (
                    <span style={{ fontSize: "0.7rem", padding: "1px 5px", background: "var(--bg-secondary)", border: "1px solid var(--border-light)", color: "var(--text-secondary)", borderRadius: 4, fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                      {activeDataSource.database_name}
                    </span>
                  )}
                </div>

                {/* Env Indicator */}
                <span
                  style={{
                    fontSize: "0.66rem",
                    fontWeight: 700,
                    padding: "1px 6px",
                    borderRadius: 4,
                    background: envBadge.bg,
                    color: envBadge.color,
                    letterSpacing: "0.02em"
                  }}
                >
                  {envBadge.label}
                </span>
              </div>

              {/* Right section: AI Ask Data, low frequency Dropdown, settings */}
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <button
                  onClick={() => handleAiContextAction("帮我分析当前数据库架构并生成数据洞察")}
                  className="btn-secondary"
                  style={{
                    height: 22,
                    padding: "0 8px",
                    fontSize: "0.72rem",
                    borderRadius: 4,
                    color: "var(--accent-indigo)",
                    borderColor: "rgba(74, 91, 192, 0.2)",
                    background: "rgba(74, 91, 192, 0.04)",
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    fontWeight: 600
                  }}
                  title="智能数据库问数 (Context-Aware)"
                >
                  <Sparkles size={11} />
                  <span>AI 问数</span>
                </button>

                {/* Low frequency More Dropdown */}
                <div style={{ position: "relative" }}>
                  <button
                    onClick={() => setShowMoreMenu(!showMoreMenu)}
                    className="btn-secondary"
                    style={{
                      height: 22,
                      padding: "0 8px",
                      fontSize: "0.72rem",
                      borderRadius: 4,
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      fontWeight: 500,
                      borderColor: showMoreMenu ? "var(--accent-indigo)" : "var(--border-light)"
                    }}
                  >
                    <MoreHorizontal size={11} />
                    <span>更多</span>
                  </button>
                  {showMoreMenu && (
                    <>
                      <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, zIndex: 998 }} onClick={() => setShowMoreMenu(false)} />
                      <div
                        style={{
                          position: "absolute",
                          top: 26,
                          right: 0,
                          background: "var(--bg-surface)",
                          border: "1px solid var(--border-light)",
                          borderRadius: 6,
                          boxShadow: "0 10px 25px -5px rgba(0,0,0,0.06), 0 8px 10px -6px rgba(0,0,0,0.06)",
                          padding: "4px 0",
                          zIndex: 999,
                          minWidth: 130,
                        }}
                      >
                        {[
                          { label: "🔬 环境配置", action: () => setShowEnvironmentsModal(true) },
                          { label: "备份管理", action: () => setShowBackupsModal(true) },
                          { label: "性能监控", action: () => setShowDashboardModal(true) },
                        ].map(item => (
                          <button
                            key={item.label}
                            onClick={() => {
                              item.action();
                              setShowMoreMenu(false);
                            }}
                            style={{
                              width: "100%",
                              padding: "6px 12px",
                              border: "none",
                              background: "transparent",
                              color: "var(--text-secondary)",
                              fontSize: "0.74rem",
                              textAlign: "left",
                              cursor: "pointer",
                            }}
                            className="hover-bg-active"
                          >
                            {item.label}
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>

                <div style={{ width: 1, height: 12, background: "var(--border-light)" }} />

                <button
                  onClick={() => setShowSettingsModal(true)}
                  className="btn-ghost"
                  style={{
                    height: 22,
                    padding: "0 6px",
                    fontSize: "0.72rem",
                    color: "var(--text-secondary)",
                    display: "flex",
                    alignItems: "center",
                    gap: 4
                  }}
                  title="管理连接与数据源"
                >
                  <Settings size={12} />
                  <span>璁剧疆</span>
                </button>
              </div>
            </div>

            {/* 鈹€鈹€ Layer 2: High-Density Secondary Toolbar (36px) 鈹€鈹€ */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                background: "var(--bg-secondary)",
                borderBottom: "1px solid var(--border-light)",
                padding: "0 12px",
                height: 36,
                flexShrink: 0,
                userSelect: "none",
                justifyContent: "space-between"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <button
                  onClick={() => handleOpenQueryTab()}
                  className="btn-secondary"
                  style={{ height: 22, padding: "0 8px", fontSize: "0.72rem", display: "flex", alignItems: "center", gap: 4, background: "var(--bg-surface)", fontWeight: 600 }}
                  title="打开全新 SQL 编辑器 (Ctrl+T)"
                >
                  <Plus size={11} style={{ color: "var(--accent-indigo)" }} />
                  <span>新建查询</span>
                </button>

                <div style={{ width: 1, height: 12, background: "var(--border-light)", margin: "0 2px" }} />

                {/* Run SQL */}
                <button
                  onClick={() => triggerActiveTabAction("execute")}
                  disabled={activeTab?.type !== "query" || activeTab?.resultState === "running"}
                  className="btn-secondary"
                  style={{ height: 22, padding: "0 8px", fontSize: "0.72rem", display: "flex", alignItems: "center", gap: 4, background: "var(--bg-surface)" }}
                  title="执行 SQL 查询 (Ctrl+Enter)"
                >
                  <Play size={11} style={{ color: "var(--accent-green)" }} />
                  <span>执行</span>
                </button>

                {/* Stop SQL */}
                <button
                  onClick={() => triggerActiveTabAction("stop")}
                  disabled={activeTab?.type !== "query" || activeTab?.resultState !== "running"}
                  className="btn-secondary"
                  style={{ height: 22, padding: "0 8px", fontSize: "0.72rem", display: "flex", alignItems: "center", gap: 4, background: "var(--bg-surface)" }}
                  title="停止当前 SQL 任务"
                >
                  <X size={11} style={{ color: "var(--accent-red)" }} />
                  <span>停止</span>
                </button>

                {/* Safety Check SQL */}
                <button
                  onClick={() => triggerActiveTabAction("validate")}
                  disabled={activeTab?.type !== "query" || activeTab?.resultState === "running"}
                  className="btn-secondary"
                  style={{ height: 22, padding: "0 8px", fontSize: "0.72rem", display: "flex", alignItems: "center", gap: 4, background: "var(--bg-surface)" }}
                  title="调用 Guardrails 校验 SQL 安全性 (Ctrl+Shift+Enter)"
                >
                  <ShieldCheck size={11} style={{ color: "var(--accent-indigo)" }} />
                  <span>校验</span>
                </button>

                {/* Format SQL */}
                <button
                  onClick={() => triggerActiveTabAction("format")}
                  disabled={activeTab?.type !== "query" || activeTab?.resultState === "running"}
                  className="btn-secondary"
                  style={{ height: 22, padding: "0 8px", fontSize: "0.72rem", display: "flex", alignItems: "center", gap: 4, background: "var(--bg-surface)" }}
                  title="格式化 SQL 关键字为大写"
                >
                  <Keyboard size={11} style={{ color: "var(--text-muted)" }} />
                  <span>格式化</span>
                </button>

                <div style={{ width: 1, height: 12, background: "var(--border-light)", margin: "0 2px" }} />

                {/* Export Data */}
                <button
                  onClick={() => triggerActiveTabAction("export")}
                  disabled={!activeTab || (activeTab.type !== "query" && activeTab.type !== "table")}
                  className="btn-secondary"
                  style={{ height: 22, padding: "0 8px", fontSize: "0.72rem", display: "flex", alignItems: "center", gap: 4, background: "var(--bg-surface)" }}
                  title="导出数据为 CSV 格式"
                >
                  <Eye size={11} />
                  <span>导出</span>
                </button>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <button
                  onClick={() => {
                    if (activeDataSource) void onRefreshSchemaTables(activeDataSource.id);
                  }}
                  disabled={!activeDataSource || loadingObjects}
                  className="btn-ghost"
                  style={{ height: 22, padding: "0 6px", fontSize: "0.72rem", display: "flex", alignItems: "center", gap: 4 }}
                  title="同步元数据缓存"
                >
                  <RefreshCw size={11} className={loadingObjects ? "animate-spin" : ""} />
                  <span>刷新结构</span>
                </button>
              </div>
            </div>

            {/* Toggle Sidebar handle when collapsed */}
            {sidebarCollapsed && (
              <button
                onClick={() => setSidebarCollapsed(false)}
                style={{
                  position: "absolute",
                  left: 0,
                  top: 78,
                  width: 18,
                  height: 28,
                  borderRadius: "0 6px 6px 0",
                  border: "1px solid var(--border-light)",
                  borderLeft: "none",
                  background: "var(--bg-surface)",
                  color: "var(--text-secondary)",
                  display: "grid",
                  placeItems: "center",
                  cursor: "pointer",
                  zIndex: 99,
                  boxShadow: "2px 0 6px rgba(0,0,0,0.05)"
                }}
                title="鏄剧ず渚ф爮"
              >
                <ChevronRight size={12} />
              </button>
            )}

            {/* 鈹€鈹€ Layer 3: High-Density Tab Bar (32px) 鈹€鈹€ */}
            {tabs.length > 0 && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  background: "var(--bg-secondary)",
                  borderBottom: "1px solid var(--border-light)",
                  padding: "4px 8px 0",
                  overflowX: "auto",
                  flexShrink: 0,
                  height: 32
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 4, overflowX: "auto", height: "100%" }}>
                  {tabs.map((tab) => {
                    const isActive = tab.id === activeTabId;
                    return (
                      <div
                        key={tab.id}
                        onClick={() => handleSelectTab(tab.id)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          padding: "0 10px",
                          borderRadius: "4px 4px 0 0",
                          background: isActive ? "var(--bg-surface)" : "transparent",
                          border: "1px solid",
                          borderColor: isActive ? "var(--border-light)" : "transparent",
                          borderBottomColor: isActive ? "var(--bg-surface)" : "transparent",
                          color: isActive ? "var(--accent-indigo)" : "var(--text-secondary)",
                          cursor: "pointer",
                          fontSize: "0.74rem",
                          fontWeight: isActive ? 700 : 500,
                          minWidth: "fit-content",
                          transition: "all 0.1s",
                          height: "100%"
                        }}
                      >
                        {tab.resultState === "running" ? (
                          <span className="animate-spin" style={{ fontSize: "0.68rem" }}>↻</span>
                        ) : tab.type === "query" ? (
                          <Terminal size={11} style={{ opacity: isActive ? 1 : 0.6 }} />
                        ) : (
                          <Table2 size={11} style={{ opacity: isActive ? 1 : 0.6 }} />
                        )}

                        <span style={{ maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {tab.title}{tab.dirty && tab.type === "table" ? "*" : ""}
                        </span>

                        {tab.dirty && tab.type === "query" && (
                          <span style={{ color: "var(--accent-amber)", fontSize: "0.65rem" }}>●</span>
                        )}

                        <button
                          onClick={(e) => handleCloseTab(tab.id, e)}
                          className="btn-ghost"
                          style={{ padding: 1, borderRadius: "50%", display: "grid", placeItems: "center", color: "var(--text-muted)" }}
                        >
                          <X size={10} />
                        </button>
                      </div>
                    );
                  })}

                  <button
                    className="btn-ghost"
                    onClick={() => handleOpenQueryTab()}
                    style={{ padding: "2px 6px", display: "flex", alignItems: "center" }}
                    title="新建 SQL 编辑器 (Ctrl+T)"
                  >
                    <Plus size={12} />
                  </button>
                </div>
              </div>
            )}

            {/* 鈹€鈹€ Active Tab Viewport Area 鈹€鈹€ */}
            <div style={{ flex: 1, overflow: "hidden", minHeight: 0, position: "relative" }}>
              {tabs.length === 0 ? (
                /* Premium Empty Workspace Dashboard */
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100%",
                    padding: 30,
                    overflowY: "auto",
                    background: "radial-gradient(circle at top, var(--bg-surface) 0%, var(--bg-primary) 100%)",
                    textAlign: "center"
                  }}
                >
                  <div
                    className="lab-card animate-fade-in stagger"
                    style={{
                      maxWidth: 620,
                      width: "100%",
                      padding: "36px 30px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 20,
                      border: "1px solid var(--border-light)",
                      borderRadius: 12,
                      background: "var(--bg-surface)",
                      boxShadow: "0 20px 40px rgba(0, 0, 0, 0.03)"
                    }}
                  >
                    {/* Visual Identity */}
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
                      <div
                        style={{
                          width: 48,
                          height: 48,
                          borderRadius: 12,
                          background: "rgba(74, 91, 192, 0.08)",
                          display: "grid",
                          placeItems: "center"
                        }}
                      >
                        <Code2 size={24} style={{ color: "var(--accent-indigo)" }} />
                      </div>
                      <div>
                        <h2 className="text-display" style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
                          DATABOX 智能探索实验室
                        </h2>
                        <p style={{ color: "var(--text-secondary)", fontSize: "0.82rem", maxWidth: 420, margin: "0 auto", lineHeight: 1.4 }}>
                          本地优先的 MySQL、PostgreSQL 与 SQLite 数据实验室。在左侧对象树中连接库、双击查表，或者使用下方快捷指令开启会话。
                        </p>
                      </div>
                    </div>

                    <div style={{ height: "1px", background: "var(--border-light)" }} />

                    {/* Quick Actions Grid */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, textAlign: "left" }}>
                      <button
                        onClick={() => handleOpenQueryTab()}
                        className="hover-lift"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          padding: 12,
                          background: "var(--bg-secondary)",
                          border: "1px solid var(--border-light)",
                          borderRadius: 8,
                          cursor: "pointer",
                          textAlign: "left"
                        }}
                      >
                        <Terminal size={16} style={{ color: "var(--accent-indigo)" }} />
                        <div>
                          <h4 style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: 2 }}>
                            新建 SQL 查询会话
                          </h4>
                          <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", lineHeight: 1.3 }}>
                            开启智能补全、DDL 审计与执行计划可视化
                          </p>
                        </div>
                      </button>

                      <button
                        onClick={() => handleAiContextAction("帮我分析当前数据库架构并生成数据洞察")}
                        className="hover-lift"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          padding: 12,
                          background: "rgba(74, 91, 192, 0.04)",
                          border: "1px solid rgba(74, 91, 192, 0.15)",
                          borderRadius: 8,
                          cursor: "pointer",
                          textAlign: "left"
                        }}
                      >
                        <Sparkles size={16} style={{ color: "var(--accent-indigo)" }} />
                        <div>
                          <h4 style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--accent-indigo)", marginBottom: 2 }}>
                            智能问数与找表
                          </h4>
                          <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", lineHeight: 1.3 }}>
                            使用大模型对物理表进行模糊关联定位并生成报表
                          </p>
                        </div>
                      </button>
                    </div>

                    {/* Keyboard Shortcuts Info */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 12,
                        fontSize: "0.72rem",
                        color: "var(--text-muted)",
                        background: "rgba(0,0,0,0.01)",
                        padding: "8px",
                        borderRadius: 6,
                        border: "1px dashed var(--border-light)"
                      }}
                    >
                      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <Keyboard size={11} />
                        <span>快捷操作:</span>
                      </span>
                      <span>新建查询: <kbd style={{ background: "var(--bg-secondary)", padding: "1px 3px", borderRadius: 3, border: "1px solid var(--border-medium)" }}>Ctrl + T</kbd></span>
                      <span>执行 SQL: <kbd style={{ background: "var(--bg-secondary)", padding: "1px 3px", borderRadius: 3, border: "1px solid var(--border-medium)" }}>Ctrl + Enter</kbd></span>
                    </div>
                  </div>
                </div>
              ) : (
                /* Render active tab viewport based on type */
                <div style={{ height: "100%", width: "100%" }}>
                  {activeTab?.type === "query" && activeDataSource && (
                    /* Independent Query Page console */
                    <ErrorBoundary title="SQL 编辑器加载错误">
                      <Suspense fallback={<div className="skeleton" style={{ height: "100%", minHeight: 320, borderRadius: 8 }} />}>
                        <QueryPage
                          key={activeTab.id}
                          datasource={activeDataSource}
                          initialDraft={activeTab.sqlDraft ? { sql: activeTab.sqlDraft, nonce: 1 } : null}
                          actionTrigger={activeTab.actionTrigger}
                          onStateChange={handleActiveQueryStateChange}
                        />
                      </Suspense>
                    </ErrorBoundary>
                  )}

                  {activeTab?.type === "table" && activeTab.tableName && activeDataSource && (
                    /* Fully integrated modular Table Detail board */
                    <div style={{ display: "flex", flexDirection: "column", height: "100%", width: "100%", overflow: "hidden" }}>

                      {/* High-density horizontal horizontal sub-tab bar inside Table Tab */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          background: "var(--bg-surface)",
                          borderBottom: "1px solid var(--border-light)",
                          padding: "6px 20px 0",
                          gap: 8,
                          flexShrink: 0
                        }}
                      >
                        {[
                          { id: "data", label: "数据" },
                          { id: "schema", label: "字段" },
                          { id: "er", label: "ER 关系" },
                          { id: "design", label: "DDL 变更" }
                        ].map(sub => {
                          const isSubActive = (activeTab.activeSubTab || "data") === sub.id;
                          return (
                            <button
                              key={sub.id}
                              onClick={() => handleSwitchSubTab(activeTab.id, sub.id as NonNullable<WorkbenchTab["activeSubTab"]>)}
                              style={{
                                padding: "6px 12px 8px",
                                border: "none",
                                background: "transparent",
                                borderBottom: isSubActive ? "2px solid var(--accent-indigo)" : "2px solid transparent",
                                color: isSubActive ? "var(--accent-indigo)" : "var(--text-secondary)",
                                fontWeight: isSubActive ? 600 : 500,
                                fontSize: "0.76rem",
                                cursor: "pointer",
                                transition: "all 0.1s"
                              }}
                            >
                              {sub.label}
                            </button>
                          );
                        })}

                        {/* Table Name Context Indicator */}
                        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4, paddingBottom: 6 }}>
                          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>当前对象: <strong style={{ color: "var(--text-secondary)" }}>{activeTab.tableName}</strong></span>
                        </div>
                      </div>

                      {/* Sub tab content containers */}
                      <div style={{ flex: 1, overflow: "hidden", minHeight: 0 }}>
                    {(activeTab.activeSubTab || "data") === "data" && (
                      <ErrorBoundary title="数据大屏预览组件崩溃">
                        <Suspense fallback={<div className="skeleton" style={{ height: "100%", minHeight: 320, borderRadius: 8 }} />}>
                          <DataPage
                            datasource={activeDataSource}
                            selectedTableName={activeTab.tableName}
                            schemaTables={schemaTables}
                            onSelectTable={(name) => handleOpenTableTab(name, "data")}
                          />
                        </Suspense>
                      </ErrorBoundary>
                    )}

                    {(activeTab.activeSubTab || "data") === "schema" && (
                      <ErrorBoundary title="结构属性查看组件崩溃">
                        <Suspense fallback={<div className="skeleton" style={{ height: "100%", minHeight: 320, borderRadius: 8 }} />}>
                          <SchemaPage
                            datasource={activeDataSource}
                            initialViewTab="fields"
                            selectedTableName={activeTab.tableName}
                            onOpenSql={(sql, title) => handleOpenQueryTab(sql, title)}
                          />
                        </Suspense>
                      </ErrorBoundary>
                    )}

                    {(activeTab.activeSubTab || "data") === "er" && (
                      <ErrorBoundary title="表实体 ER 关联图崩溃">
                        <Suspense fallback={<div className="skeleton" style={{ height: "100%", minHeight: 320, borderRadius: 8 }} />}>
                          <SchemaPage
                            datasource={activeDataSource}
                            initialViewTab="er"
                            selectedTableName={activeTab.tableName}
                            onOpenSql={(sql, title) => handleOpenQueryTab(sql, title)}
                          />
                        </Suspense>
                      </ErrorBoundary>
                    )}

                    {(activeTab.activeSubTab || "data") === "design" && (
                      <ErrorBoundary title="DDL结构修改设计组件崩溃">
                        <Suspense fallback={<div className="skeleton" style={{ height: "100%", minHeight: 320, borderRadius: 8 }} />}>
                          <SchemaPage
                            datasource={activeDataSource}
                            initialViewTab="design"
                            selectedTableName={activeTab.tableName}
                            onOpenSql={(sql, title) => handleOpenQueryTab(sql, title)}
                          />
                        </Suspense>
                      </ErrorBoundary>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

        </div>
      </section>

      {/* 鈺愨晲鈺?FLOATING SLIDE-OVER AI CONTEXT ASSISTANT DRAWER 鈺愨晲鈺?*/}
      {aiPanelOpen && activeDataSource && (
        <aside
          className="animate-slide-left"
          style={{
            position: "absolute",
            top: 40, // Height of the Tab bar
            right: 0,
            bottom: 30, // Footer offset
            width: 320,
            background: "rgba(255, 255, 255, 0.9)",
            backdropFilter: "blur(14px)",
            borderLeft: "1px solid var(--border-light)",
            boxShadow: "-4px 0 24px rgba(0,0,0,0.06)",
            zIndex: 100,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden"
          }}
        >
          {/* AI Header */}
          <div
            style={{
              padding: "12px 16px",
              borderBottom: "1px solid var(--border-light)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              background: "rgba(74, 91, 192, 0.04)"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Sparkles size={14} style={{ color: "var(--accent-indigo)" }} />
              <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--text-primary)" }}>
                AI 上下文数据库助手
              </span>
            </div>
            <button
              onClick={() => setAiPanelOpen(false)}
              className="btn-ghost"
              style={{ padding: 2 }}
            >
              <X size={14} />
            </button>
          </div>

          {/* AI Context Card */}
          <div style={{ padding: "10px 16px", background: "var(--bg-secondary)", borderBottom: "1px solid var(--border-light)", fontSize: "0.7rem", color: "var(--text-secondary)" }}>
            <div style={{ marginBottom: 4 }}>
              <strong>当前库</strong> <code style={{ background: "#fff", padding: "1px 4px", borderRadius: 3 }}>{activeDataSource.database_name}</code>
            </div>
            {activeTab?.tableName && (
              <div>
                <strong>当前聚焦表</strong> <code style={{ background: "#fff", padding: "1px 4px", borderRadius: 3 }}>{activeTab.tableName}</code>
              </div>
            )}
          </div>

          {/* Prompt Conversation Area */}
          <div style={{ flex: 1, overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>

            {/* Quick AI Presets */}
            <div>
              <span style={{ fontSize: "0.68rem", fontWeight: 700, color: "var(--text-muted)", display: "block", marginBottom: 6 }}>
                快捷分析指令
              </span>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {activeTab?.tableName ? (
                  <>
                    <button
                      onClick={() => handleAiContextAction(`用物理外键和字段名，帮我生成表 ${activeTab.tableName} 关联查询其他表的 JOIN SQL，并包含主要字段说明。`)}
                      className="btn-secondary"
                      style={{ padding: "5px 8px", fontSize: "0.72rem", justifyContent: "flex-start", textAlign: "left", width: "100%" }}
                    >
                      自动生成多表关联 SQL
                    </button>
                    <button
                      onClick={() => handleAiContextAction(`分析并指出表 ${activeTab.tableName} 结构中是否有缺失索引，或者主外键关联的潜在优化风险。`)}
                      className="btn-secondary"
                      style={{ padding: "5px 8px", fontSize: "0.72rem", justifyContent: "flex-start", textAlign: "left", width: "100%" }}
                    >
                      审核优化当前表设计
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => handleAiContextAction("列出当前数据库中最常被用作关联的主键、外键表，并生成简要关系说明。")}
                      className="btn-secondary"
                      style={{ padding: "5px 8px", fontSize: "0.72rem", justifyContent: "flex-start", textAlign: "left", width: "100%" }}
                    >
                      智能检索全局 Schema 关系
                    </button>
                    <button
                      onClick={() => handleAiContextAction("用最简单的 MySQL 或 SQL 查询指令，帮我测试数据源的读写延迟，并生成诊断代码。")}
                      className="btn-secondary"
                      style={{ padding: "5px 8px", fontSize: "0.72rem", justifyContent: "flex-start", textAlign: "left", width: "100%" }}
                    >
                      数据源读写延迟探针
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Answer Display */}
            {aiResponse && (
              <div
                className="lab-card animate-fade-in"
                style={{
                  padding: 12,
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-light)",
                  fontSize: "0.78rem",
                  lineHeight: 1.5,
                  borderRadius: 8,
                  position: "relative"
                }}
              >
                <div style={{ fontSize: "0.68rem", fontWeight: 700, color: "var(--text-muted)", marginBottom: 6, display: "flex", alignItems: "center", gap: 4 }}>
                  <ShieldCheck size={11} style={{ color: "var(--accent-green)" }} />
                  <span>AI 分析与 SQL 生成:</span>
                </div>
                <pre
                  style={{
                    whiteSpace: "pre-wrap",
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.72rem",
                    color: "var(--text-primary)",
                    background: "rgba(0,0,0,0.01)",
                    padding: 8,
                    borderRadius: 4,
                    overflowX: "auto"
                  }}
                >
                  {aiResponse}
                </pre>

                {aiResponse.includes("SELECT") && (
                  <button
                    onClick={() => {
                      const match = aiResponse.match(/SELECT[\s\S]+?;/i);
                      handleOpenQueryTab(match ? match[0] : aiResponse, "AI 生成查询");
                    }}
                    className="btn-primary"
                    style={{ width: "100%", marginTop: 8, padding: "4px 0", fontSize: "0.72rem", justifyContent: "center" }}
                  >
                    <Play size={10} />
                    将生成 SQL 发送到新查询窗口
                  </button>
                )}
              </div>
            )}

            {aiLoading && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, padding: "20px 0", color: "var(--text-muted)" }}>
                <span className="animate-spin" style={{ fontSize: 18 }}>↻</span>
                <span style={{ fontSize: "0.74rem" }}>正在进行知识检索与智能推理...</span>
              </div>
            )}

          </div>

          {/* Prompt Input Form */}
          <form
            onSubmit={handleAskGeneralAi}
            style={{
              padding: 12,
              borderTop: "1px solid var(--border-light)",
              background: "rgba(0, 0, 0, 0.01)",
              display: "flex",
              flexDirection: "column",
              gap: 8
            }}
          >
            <textarea
              className="input-field"
              placeholder="问我关于库、表结构，或者生成 SQL..."
              value={aiPrompt}
              onChange={(e) => setAiPrompt(e.target.value)}
              style={{ height: 60, fontSize: "0.78rem", resize: "none" }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void handleAskGeneralAi(e);
                }
              }}
            />
            <button
              type="submit"
              className="btn-primary"
              disabled={aiLoading || !aiPrompt.trim()}
              style={{ padding: "6px 0", fontSize: "0.76rem", width: "100%", justifyContent: "center" }}
            >
              发送指令
            </button>
          </form>

        </aside>
      )}

      {/* 鈺愨晲鈺?1. DATA SOURCES MANAGER (SETTINGS) MODAL 鈺愨晲鈺?*/}
      {showSettingsModal && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(15, 23, 42, 0.4)", backdropFilter: "blur(4px)", zIndex: 1000, display: "grid", placeItems: "center" }}>
          <div style={{ background: "var(--bg-surface)", width: "80%", height: "85%", borderRadius: 12, border: "1px solid var(--border-light)", display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: "0 20px 50px rgba(0,0,0,0.15)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 20px", borderBottom: "1px solid var(--border-light)", background: "var(--bg-secondary)" }}>
              <span style={{ fontWeight: 700, fontSize: "0.82rem", color: "var(--text-primary)" }}>连接管理器（数据源设置）</span>
              <button onClick={() => setShowSettingsModal(false)} className="btn-ghost" style={{ padding: 4 }}><X size={16} /></button>
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
              <DataSourcesPage
                onSelectDataSource={(ds) => {
                  setActiveDataSource(ds);
                  setShowSettingsModal(false);
                }}
                activeDataSource={activeDataSource}
                activeProject={activeProject}
                onRefreshDatasources={onRefreshDatasources}
              />
            </div>
          </div>
        </div>
      )}

      {/* 鈺愨晲鈺?2. ENVIRONMENTS CONFIG MODAL 鈺愨晲鈺?*/}
      {showEnvironmentsModal && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(15, 23, 42, 0.4)", backdropFilter: "blur(4px)", zIndex: 1000, display: "grid", placeItems: "center" }}>
          <div style={{ background: "var(--bg-surface)", width: "80%", height: "85%", borderRadius: 12, border: "1px solid var(--border-light)", display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: "0 20px 50px rgba(0,0,0,0.15)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 20px", borderBottom: "1px solid var(--border-light)", background: "var(--bg-secondary)" }}>
              <span style={{ fontWeight: 700, fontSize: "0.82rem", color: "var(--text-primary)" }}>环境配置</span>
              <button onClick={() => setShowEnvironmentsModal(false)} className="btn-ghost" style={{ padding: 4 }}><X size={16} /></button>
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
              <EnvironmentsPage
                activeProject={activeProject}
                onRefreshDatasources={onRefreshDatasources}
                onSelectDataSource={(ds) => {
                  setActiveDataSource(ds);
                  setShowEnvironmentsModal(false);
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* 鈺愨晲鈺?3. BACKUPS MANAGER MODAL 鈺愨晲鈺?*/}
      {showBackupsModal && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(15, 23, 42, 0.4)", backdropFilter: "blur(4px)", zIndex: 1000, display: "grid", placeItems: "center" }}>
          <div style={{ background: "var(--bg-surface)", width: "80%", height: "85%", borderRadius: 12, border: "1px solid var(--border-light)", display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: "0 20px 50px rgba(0,0,0,0.15)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 20px", borderBottom: "1px solid var(--border-light)", background: "var(--bg-secondary)" }}>
              <span style={{ fontWeight: 700, fontSize: "0.82rem", color: "var(--text-primary)" }}>备份与恢复管理器</span>
              <button onClick={() => setShowBackupsModal(false)} className="btn-ghost" style={{ padding: 4 }}><X size={16} /></button>
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
              <BackupsPage
                activeProject={activeProject}
                datasources={datasources}
                activeDataSource={activeDataSource}
              />
            </div>
          </div>
        </div>
      )}

      {/* 鈺愨晲鈺?4. PERFORMANCE MONITORING DASHBOARD MODAL 鈺愨晲鈺?*/}
      {showDashboardModal && activeDataSource && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(15, 23, 42, 0.4)", backdropFilter: "blur(4px)", zIndex: 1000, display: "grid", placeItems: "center" }}>
          <div style={{ background: "var(--bg-surface)", width: "80%", height: "85%", borderRadius: 12, border: "1px solid var(--border-light)", display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: "0 20px 50px rgba(0,0,0,0.15)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 20px", borderBottom: "1px solid var(--border-light)", background: "var(--bg-secondary)" }}>
              <span style={{ fontWeight: 700, fontSize: "0.82rem", color: "var(--text-primary)" }}>鎬ц兘鐩戞帶闈㈡澘</span>
              <button onClick={() => setShowDashboardModal(false)} className="btn-ghost" style={{ padding: 4 }}><X size={16} /></button>
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
              <Suspense fallback={<div className="skeleton" style={{ height: 240, borderRadius: 8 }} />}>
                <DashboardPage datasource={activeDataSource} />
              </Suspense>
            </div>
          </div>
        </div>
      )}

      {/* 鈺愨晲鈺?5. CREATE NEW PROJECT DIALOG 鈺愨晲鈺?*/}
      <PromptDialog
        open={showCreateProject}
        title="创建新项目"
        placeholder="杈撳叆椤圭洰鍚嶇О"
        onConfirm={(name) => {
          setShowCreateProject(false);
          void onCreateProject(name);
        }}
        onCancel={() => setShowCreateProject(false)}
      />

    </div>
  );
};
