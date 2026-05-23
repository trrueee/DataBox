import type { CSSProperties, ReactNode } from "react";

interface LabCardProps {
  children: ReactNode;
  accent?: boolean;
  elevated?: boolean;
  hover?: boolean;
  className?: string;
  style?: CSSProperties;
  onClick?: () => void;
}

export function LabCard({ children, accent, elevated, hover, className, style, onClick }: LabCardProps) {
  const cls = [
    accent ? "lab-card-accent" : elevated ? "lab-card-elevated" : "lab-card",
    hover ? "hover-lift" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={cls}
      style={{ cursor: onClick ? "pointer" : undefined, ...style }}
      onClick={onClick}
    >
      {children}
    </div>
  );
}
