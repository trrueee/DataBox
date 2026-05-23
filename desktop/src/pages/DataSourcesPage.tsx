import type { MouseEvent } from "react";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import type { DataSource } from "../lib/api";
import { StatusIndicator } from "../components/StatusIndicator";

interface DataSourcesPageProps {
  onSelectDataSource: (ds: DataSource | null) => void;
  activeDataSource: DataSource | null;
  onRefreshDatasources: () => Promise<void>;
}

export const DataSourcesPage = ({
  onSelectDataSource,
  activeDataSource,
  onRefreshDatasources,
}: DataSourcesPageProps) => {
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [testResult, setTestResult] = useState<{
    status: "idle" | "testing" | "success" | "error";
    message: string;
    details?: { serverVersion?: string; readonly?: boolean; tablesCount?: number };
  }>({ status: "idle", message: "" });
  const [form, setForm] = useState({
    name: "",
    host: "",
    port: 3306,
    database_name: "",
    username: "",
    password: "",
  });

  useEffect(() => {
    void fetchDataSources();
  }, []);

  const fetchDataSources = async () => {
    try {
      setLoading(true);
      setDataSources(await api.listDatasources());
    } finally {
      setLoading(false);
    }
  };

  const syncLists = async () => {
    await fetchDataSources();
    await onRefreshDatasources();
  };

  const updateForm = (key: keyof typeof form, value: string | number) => {
    setForm((c) => ({ ...c, [key]: value }));
  };

  const handleTestConnection = async () => {
    if (!form.host || !form.database_name || !form.username) {
      setTestResult({ status: "error", message: "请先填写主机、数据库名和用户名。" });
      return;
    }
    setTestResult({ status: "testing", message: "正在测试连接..." });
    try {
      const result = await api.testConnection(form);
      setTestResult({ status: "success", message: result.message ?? "连接成功。", details: result });
    } catch (error: any) {
      setTestResult({ status: "error", message: error.message ?? "连接测试失败。" });
    }
  };

  const resetForm = () => {
    setForm({ name: "", host: "", port: 3306, database_name: "", username: "", password: "" });
    setFormError("");
    setTestResult({ status: "idle", message: "" });
  };

  const handleCreateDataSource = async () => {
    if (!form.name || !form.host || !form.database_name || !form.username || !form.password) {
      setFormError("请完整填写必填项。");
      return;
    }
    try {
      setSubmitting(true);
      setFormError("");
      const created = await api.createDatasource(form);
      setSyncingId(created.id);
      await api.syncSchema(created.id);
      await syncLists();
      resetForm();
      setShowAddForm(false);
      const refreshed = await api.listDatasources();
      setDataSources(refreshed);
      onSelectDataSource(refreshed.find((item) => item.id === created.id) ?? null);
    } catch (error: any) {
      setFormError(error.message ?? "保存失败。");
    } finally {
      setSubmitting(false);
      setSyncingId(null);
    }
  };

  const handleSyncSchema = async (id: string, event: MouseEvent) => {
    event.stopPropagation();
    try {
      setSyncingId(id);
      await api.syncSchema(id);
      await syncLists();
    } finally {
      setSyncingId(null);
    }
  };

  const handleDeleteDataSource = async (id: string, event: MouseEvent) => {
    event.stopPropagation();
    if (!window.confirm("确认删除此数据源？")) return;
    await api.deleteDatasource(id);
    await syncLists();
    if (activeDataSource?.id === id) onSelectDataSource(null);
  };

  const statusType = (ds: DataSource) =>
    ds.last_sync_status === "success" ? "success" : ds.last_sync_status === "failed" ? "error" : "idle";

  return (
    <div
      className="animate-fade-in"
      style={{ display: "flex", flexDirection: "column", gap: 20, height: "100%", overflow: "auto" }}
    >
      {/* Page Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h2 className="text-display" style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--text-primary)" }}>
            连接管理器
          </h2>
          <p style={{ color: "var(--text-secondary)", marginTop: 4, fontSize: "0.9rem" }}>
            管理远程 MySQL 连接，测试可用性，同步本地 Schema 缓存
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowAddForm((v) => !v)}>
          {showAddForm ? <X size={15} /> : <Plus size={15} />}
          {showAddForm ? "收起" : "添加连接"}
        </button>
      </div>

      {/* Add Form */}
      {showAddForm && (
        <div className="lab-card animate-slide-down" style={{ padding: 24 }}>
          <h3 className="text-display" style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: 20 }}>
            新增 MySQL 数据源
          </h3>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <label className="field-label">连接名称</label>
              <input
                className="input-field"
                value={form.name}
                onChange={(e) => updateForm("name", e.target.value)}
                placeholder="例：生产只读库"
              />
            </div>
            <div>
              <label className="field-label">主机地址</label>
              <input
                className="input-field"
                value={form.host}
                onChange={(e) => updateForm("host", e.target.value)}
                placeholder="db.example.com"
              />
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "120px 1fr 1fr", gap: 16, marginTop: 16 }}>
            <div>
              <label className="field-label">端口</label>
              <input
                className="input-field"
                type="number"
                value={form.port}
                onChange={(e) => updateForm("port", Number(e.target.value) || 3306)}
              />
            </div>
            <div>
              <label className="field-label">数据库名</label>
              <input
                className="input-field"
                value={form.database_name}
                onChange={(e) => updateForm("database_name", e.target.value)}
              />
            </div>
            <div>
              <label className="field-label">用户名</label>
              <input
                className="input-field"
                value={form.username}
                onChange={(e) => updateForm("username", e.target.value)}
              />
            </div>
          </div>

          <div style={{ marginTop: 16 }}>
            <label className="field-label">密码</label>
            <input
              className="input-field"
              type="password"
              value={form.password}
              onChange={(e) => updateForm("password", e.target.value)}
            />
          </div>

          {formError && (
            <div style={{ marginTop: 12 }}>
              <StatusIndicator type="error" label={formError} />
            </div>
          )}

          {/* Test Result */}
          {testResult.status !== "idle" && (
            <div
              className="lab-card-accent animate-slide-down"
              style={{
                marginTop: 16,
                padding: 14,
                borderLeftColor:
                  testResult.status === "success"
                    ? "var(--accent-green)"
                    : testResult.status === "error"
                      ? "var(--accent-red)"
                      : "var(--accent-amber)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontWeight: 600,
                  fontSize: "0.88rem",
                  color:
                    testResult.status === "success"
                      ? "var(--accent-green)"
                      : testResult.status === "error"
                        ? "var(--accent-red)"
                        : "var(--text-secondary)",
                }}
              >
                {testResult.status === "success" ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                {testResult.message}
              </div>
              {testResult.details && (
                <div
                  style={{
                    marginTop: 8,
                    display: "flex",
                    gap: 20,
                    fontSize: "0.82rem",
                    color: "var(--text-secondary)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  <span>Server: {testResult.details.serverVersion ?? "-"}</span>
                  <span>Tables: {testResult.details.tablesCount ?? "-"}</span>
                  <span>ReadOnly: {testResult.details.readonly ? "Yes" : "No"}</span>
                </div>
              )}
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20 }}>
            <button className="btn-secondary" onClick={handleTestConnection} disabled={submitting}>
              测试连接
            </button>
            <button className="btn-primary" onClick={handleCreateDataSource} disabled={submitting}>
              {submitting ? "保存中..." : "保存并同步 Schema"}
            </button>
          </div>
        </div>
      )}

      {/* Connection List */}
      <div style={{ flex: 1 }}>
        <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
          已保存连接
          <span style={{ fontWeight: 400, color: "var(--text-muted)", fontSize: "0.85rem" }}>
            ({dataSources.length})
          </span>
        </h3>

        {loading ? (
          <div className="stagger" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton" style={{ height: 80, borderRadius: 10 }} />
            ))}
          </div>
        ) : dataSources.length === 0 ? (
          <div className="lab-card" style={{ padding: 56, textAlign: "center" }}>
            <Database size={40} style={{ color: "var(--text-muted)", opacity: 0.3, marginBottom: 12 }} />
            <div className="empty-state-title">还没有数据源</div>
            <div className="empty-state-desc" style={{ marginTop: 4 }}>
              添加一个 MySQL 连接，开始探索你的数据
            </div>
          </div>
        ) : (
          <div className="stagger" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {dataSources.map((ds) => {
              const isActive = activeDataSource?.id === ds.id;
              const st = statusType(ds);

              return (
                <div
                  key={ds.id}
                  className="lab-card hover-lift"
                  style={{
                    padding: "16px 20px",
                    borderColor: isActive ? "var(--accent-indigo)" : undefined,
                    borderWidth: isActive ? 1.5 : 1,
                    cursor: "pointer",
                  }}
                  onClick={() => onSelectDataSource(ds)}
                >
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "minmax(0, 1.5fr) 120px 170px 100px auto",
                      gap: 16,
                      alignItems: "center",
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <Database size={15} style={{ color: isActive ? "var(--accent-indigo)" : "var(--text-muted)" }} />
                        <h4
                          style={{
                            fontSize: "0.94rem",
                            fontWeight: 600,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {ds.name}
                        </h4>
                        {isActive && <span className="tag tag-indigo">当前</span>}
                      </div>
                      <p
                        style={{
                          marginTop: 3,
                          fontSize: "0.8rem",
                          color: "var(--text-muted)",
                          fontFamily: "var(--font-mono)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {ds.host}:{ds.port} / {ds.database_name}
                      </p>
                    </div>

                    <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>{ds.username}</div>

                    <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                      {ds.last_sync_at ? new Date(ds.last_sync_at).toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "未同步"}
                    </div>

                    <StatusIndicator type={st} label={st === "success" ? "已同步" : st === "error" ? "失败" : "待同步"} />

                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
                      <button
                        className="btn-ghost"
                        onClick={(e) => handleSyncSchema(ds.id, e)}
                        disabled={syncingId === ds.id}
                        style={{ color: "var(--accent-indigo)" }}
                      >
                        <RefreshCw size={14} className={syncingId === ds.id ? "animate-spin" : ""} />
                        {syncingId === ds.id ? "同步中" : "同步"}
                      </button>
                      <button
                        className="btn-ghost"
                        onClick={(e) => handleDeleteDataSource(ds.id, e)}
                        style={{ color: "var(--accent-red)" }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
