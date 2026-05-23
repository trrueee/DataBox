interface DataTableProps {
  columns: string[];
  rows: Record<string, unknown>[];
  numericColumns?: string[];
  maxHeight?: string;
}

function isNumeric(val: unknown): boolean {
  return typeof val === "number";
}

export function DataTable({ columns, rows, numericColumns, maxHeight }: DataTableProps) {
  const numericSet = new Set(numericColumns ?? []);

  return (
    <div style={{ overflow: "auto", maxHeight: maxHeight ?? "100%" }}>
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {columns.map((col) => {
                const val = row[col];
                const isNum = numericSet.has(col) || isNumeric(val);

                if (val === null || val === undefined) {
                  return (
                    <td key={`${ri}-${col}`} className="cell-null">
                      NULL
                    </td>
                  );
                }

                return (
                  <td key={`${ri}-${col}`} className={isNum ? "cell-number" : undefined}>
                    {String(val)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
