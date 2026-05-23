import { useEffect, useRef } from "react";
import type { ERDiagramData } from "../lib/api";

interface ErDiagramProps {
  data: ERDiagramData;
}

interface LayoutNode {
  id: string;
  label: string;
  fields: { name: string; is_pk: boolean; is_fk: boolean }[];
  x: number;
  y: number;
  w: number;
  h: number;
}

const NODE_W = 210;
const ROW_H = 22;
const HEADER_H = 36;
const PAD = 60;

export function ErDiagram({ data }: ErDiagramProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.nodes.length === 0) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;

    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);

    // Layout nodes in a grid
    const cols = Math.ceil(Math.sqrt(data.nodes.length));
    const layoutNodes: LayoutNode[] = data.nodes.map((node, i) => {
      const h = HEADER_H + node.fields.length * ROW_H + 12;
      const col = i % cols;
      const row = Math.floor(i / cols);
      return {
        id: node.id,
        label: node.label,
        fields: node.fields,
        x: PAD + col * (NODE_W + PAD),
        y: PAD + row * (h + PAD),
        w: NODE_W,
        h,
      };
    });

    const totalW = cols * (NODE_W + PAD) + PAD;
    const totalH = Math.ceil(data.nodes.length / cols) * (Math.max(...layoutNodes.map((n) => n.h)) + PAD) + PAD;
    canvas.style.width = `${Math.max(totalW, rect.width)}px`;
    canvas.style.height = `${Math.max(totalH, rect.height)}px`;

    // Clear
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Colors (matching light lab theme)
    const bgCard = "#FFFFFF";
    const borderCard = "#D4D2CC";
    const headerBg = "#F3F2EE";
    const textPrimary = "#1A1A1C";
    const textSecondary = "#5C5D60";
    const accentTeal = "#0D7377";
    const accentAmber = "#B45309";

    const nodeMap = new Map(layoutNodes.map((n) => [n.label, n]));

    // Draw edges
    for (const edge of data.edges) {
      const source = nodeMap.get(edge.source);
      const target = nodeMap.get(edge.target);
      if (!source || !target) continue;

      const x1 = source.x + source.w;
      const y1 = source.y + HEADER_H + 10;
      const x2 = target.x;
      const y2 = target.y + HEADER_H + 10;

      ctx.beginPath();
      ctx.moveTo(x1, y1);
      const cpX = (x1 + x2) / 2;
      ctx.bezierCurveTo(cpX, y1, cpX, y2, x2, y2);
      ctx.strokeStyle = accentTeal;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 3]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Arrow at target
      const arrowSize = 5;
      ctx.beginPath();
      ctx.moveTo(x2, y2);
      ctx.lineTo(x2 - arrowSize, y2 - arrowSize);
      ctx.lineTo(x2 - arrowSize, y2 + arrowSize);
      ctx.closePath();
      ctx.fillStyle = accentTeal;
      ctx.fill();
    }

    // Draw nodes
    for (const node of layoutNodes) {
      const r = 8;

      // Shadow
      ctx.shadowColor = "rgba(0,0,0,0.08)";
      ctx.shadowBlur = 8;
      ctx.shadowOffsetY = 2;

      // Card body
      ctx.beginPath();
      ctx.moveTo(node.x + r, node.y);
      ctx.lineTo(node.x + node.w - r, node.y);
      ctx.quadraticCurveTo(node.x + node.w, node.y, node.x + node.w, node.y + r);
      ctx.lineTo(node.x + node.w, node.y + node.h - r);
      ctx.quadraticCurveTo(node.x + node.w, node.y + node.h, node.x + node.w - r, node.y + node.h);
      ctx.lineTo(node.x + r, node.y + node.h);
      ctx.quadraticCurveTo(node.x, node.y + node.h, node.x, node.y + node.h - r);
      ctx.lineTo(node.x, node.y + r);
      ctx.quadraticCurveTo(node.x, node.y, node.x + r, node.y);
      ctx.closePath();
      ctx.fillStyle = bgCard;
      ctx.fill();
      ctx.strokeStyle = borderCard;
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.shadowColor = "transparent";
      ctx.shadowBlur = 0;
      ctx.shadowOffsetY = 0;

      // Header background
      ctx.beginPath();
      ctx.moveTo(node.x + r, node.y);
      ctx.lineTo(node.x + node.w - r, node.y);
      ctx.quadraticCurveTo(node.x + node.w, node.y, node.x + node.w, node.y + r);
      ctx.lineTo(node.x + node.w, node.y + HEADER_H);
      ctx.lineTo(node.x, node.y + HEADER_H);
      ctx.lineTo(node.x, node.y + r);
      ctx.quadraticCurveTo(node.x, node.y, node.x + r, node.y);
      ctx.closePath();
      ctx.fillStyle = headerBg;
      ctx.fill();

      // Header bottom line
      ctx.beginPath();
      ctx.moveTo(node.x, node.y + HEADER_H);
      ctx.lineTo(node.x + node.w, node.y + HEADER_H);
      ctx.strokeStyle = borderCard;
      ctx.lineWidth = 1;
      ctx.stroke();

      // Table name
      ctx.font = "600 13px Inter, sans-serif";
      ctx.fillStyle = textPrimary;
      ctx.fillText(node.label, node.x + 12, node.y + 24);

      // Fields
      node.fields.forEach((field, fi) => {
        const fy = node.y + HEADER_H + fi * ROW_H + 14;
        const icon = field.is_pk ? "◆" : field.is_fk ? "◇" : " ";
        ctx.font = "400 11px 'JetBrains Mono', monospace";

        // PK/FK icon
        if (field.is_pk) {
          ctx.fillStyle = accentAmber;
          ctx.fillText(icon, node.x + 10, fy);
        } else if (field.is_fk) {
          ctx.fillStyle = accentTeal;
          ctx.fillText(icon, node.x + 10, fy);
        }

        ctx.fillStyle = field.is_pk ? textPrimary : textSecondary;
        ctx.fillText(field.name, node.x + 24, fy);
      });
    }
  }, [data]);

  if (data.nodes.length === 0) return null;

  return (
    <div style={{ width: "100%", height: "100%", overflow: "auto", background: "#FAF9F6" }}>
      <canvas
        ref={canvasRef}
        style={{ display: "block", minWidth: "100%", minHeight: "100%" }}
      />
    </div>
  );
}
