import { AlertTriangle } from "lucide-react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "info";
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "确认",
  cancelLabel = "取消",
  variant = "info",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;

  const confirmBg =
    variant === "danger"
      ? "var(--accent-red)"
      : variant === "warning"
        ? "var(--accent-amber)"
        : "var(--accent-indigo)";

  const iconColor =
    variant === "danger"
      ? "var(--accent-red)"
      : variant === "warning"
        ? "var(--accent-amber)"
        : "var(--accent-indigo)";

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0, 0, 0, 0.5)",
        backdropFilter: "blur(4px)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 9998,
      }}
      onClick={onCancel}
    >
      <div
        className="animate-slide-down"
        style={{
          background: "var(--bg-surface)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-xl)",
          width: "min(440px, 90vw)",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: "24px 24px 16px" }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "var(--radius-md)",
                background:
                  variant === "danger"
                    ? "var(--accent-red-light)"
                    : variant === "warning"
                      ? "var(--accent-amber-light)"
                      : "var(--accent-indigo-light)",
                display: "grid",
                placeItems: "center",
                flexShrink: 0,
              }}
            >
              <AlertTriangle size={18} style={{ color: iconColor }} />
            </div>
            <div>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: 6 }}>{title}</h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {message}
              </p>
            </div>
          </div>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
            padding: "12px 24px",
            borderTop: "1px solid var(--border-light)",
            background: "var(--bg-secondary)",
          }}
        >
          <button className="btn-secondary" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: "8px 16px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              fontWeight: 600,
              fontSize: "0.85rem",
              color: "#fff",
              background: confirmBg,
              cursor: "pointer",
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
