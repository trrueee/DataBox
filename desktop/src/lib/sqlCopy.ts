export type TableRow = Record<string, unknown>;

export function quoteIdentifier(name: string): string {
  return `\`${String(name).replace(/`/g, "``")}\``;
}

export function normalizeCopyValue(value: unknown): string {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "bigint" || typeof value === "boolean") {
    return String(value);
  }
  if (value instanceof Date) return value.toISOString();
  return JSON.stringify(value);
}

export function formatSqlValue(value: unknown): string {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "number" || typeof value === "bigint") return String(value);
  if (typeof value === "boolean") return value ? "1" : "0";
  if (value instanceof Date) return `'${value.toISOString().replace(/'/g, "''")}'`;

  const raw = typeof value === "string" ? value : JSON.stringify(value);
  return `'${raw.replace(/\\/g, "\\\\").replace(/'/g, "''")}'`;
}

export function buildRowJson(columns: string[], row: TableRow): string {
  const ordered: TableRow = {};
  for (const column of columns) {
    ordered[column] = row[column] ?? null;
  }
  return JSON.stringify(ordered, null, 2);
}

export function buildInsertSql(
  tableName: string,
  columns: string[],
  row: TableRow,
  databaseName?: string,
): string {
  const qualifiedTable = databaseName
    ? `${quoteIdentifier(databaseName)}.${quoteIdentifier(tableName)}`
    : quoteIdentifier(tableName);
  const columnList = columns.map(quoteIdentifier).join(", ");
  const valueList = columns.map((column) => formatSqlValue(row[column])).join(", ");
  return `INSERT INTO ${qualifiedTable} (${columnList})\nVALUES (${valueList});`;
}
