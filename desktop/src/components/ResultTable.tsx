interface ResultTableProps {
  columns: string[];
  rows: Record<string, unknown>[];
}

export function ResultTable({ columns, rows }: ResultTableProps) {
  return (
    <div style={{ overflow: "auto", maxHeight: "100%" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border-glass)" }}>
            {columns.map((column) => (
              <th
                key={column}
                style={{ padding: "10px 12px", textAlign: "left", color: "var(--text-secondary)" }}
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              {columns.map((column) => (
                <td key={`${rowIndex}-${column}`} style={{ padding: "10px 12px" }}>
                  {row[column] === null ? (
                    <span style={{ color: "var(--text-muted)" }}>null</span>
                  ) : (
                    String(row[column])
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
