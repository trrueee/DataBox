import { useMemo, useState } from "react";

export type SortState = {
  column: string;
  direction: "asc" | "desc";
} | null;

export type FilterMode = "contains" | "is_null" | "is_not_null";

export type ColumnFilter = {
  column: string;
  mode: FilterMode;
  value?: string;
};

interface UseDataTableViewProps {
  columns: string[];
  rows: Record<string, unknown>[];
}

export function useDataTableView({ columns, rows }: UseDataTableViewProps) {
  const [sortState, setSortState] = useState<SortState>(null);
  const [filters, setFilters] = useState<Record<string, ColumnFilter>>({});
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(new Set());

  // 1. Columns filtering
  const visibleColumns = useMemo(() => {
    return columns.filter((col) => !hiddenColumns.has(col));
  }, [columns, hiddenColumns]);

  // 2. Filter logic
  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      for (const col of Object.keys(filters)) {
        const filter = filters[col];
        const val = row[col];
        
        if (filter.mode === "is_null") {
          if (val !== null && val !== undefined) return false;
        } else if (filter.mode === "is_not_null") {
          if (val === null || val === undefined) return false;
        } else if (filter.mode === "contains") {
          if (!filter.value) continue;
          if (val === null || val === undefined) return false;
          const strVal = String(val).toLowerCase();
          const strSearch = filter.value.toLowerCase();
          if (!strVal.includes(strSearch)) return false;
        }
      }
      return true;
    });
  }, [rows, filters]);

  // 3. Sort logic
  const sortedRows = useMemo(() => {
    if (!sortState) return filteredRows;
    const { column, direction } = sortState;

    return [...filteredRows].sort((a, b) => {
      const valA = a[column];
      const valB = b[column];

      // NULLs go to the end for both asc and desc
      const isNullA = valA === null || valA === undefined;
      const isNullB = valB === null || valB === undefined;

      if (isNullA && isNullB) return 0;
      if (isNullA) return 1; // A goes to the end
      if (isNullB) return -1; // B goes to the end

      // Date parsing check
      const isDateA = valA instanceof Date || (typeof valA === "string" && !isNaN(Date.parse(valA)) && isNaN(Number(valA)));
      const isDateB = valB instanceof Date || (typeof valB === "string" && !isNaN(Date.parse(valB)) && isNaN(Number(valB)));

      let comparison = 0;

      if (typeof valA === "number" && typeof valB === "number") {
        comparison = valA - valB;
      } else if (isDateA && isDateB) {
        const timeA = new Date(valA as any).getTime();
        const timeB = new Date(valB as any).getTime();
        comparison = timeA - timeB;
      } else {
        comparison = String(valA).localeCompare(String(valB), "zh-Hans-CN", { numeric: true });
      }

      return direction === "asc" ? comparison : -comparison;
    });
  }, [filteredRows, sortState]);

  const setFilter = (column: string, mode: FilterMode, value?: string) => {
    setFilters((prev) => ({
      ...prev,
      [column]: { column, mode, value },
    }));
  };

  const clearFilter = (column: string) => {
    setFilters((prev) => {
      const next = { ...prev };
      delete next[column];
      return next;
    });
  };

  const clearAllFilters = () => {
    setFilters({});
  };

  const toggleHideColumn = (column: string) => {
    setHiddenColumns((prev) => {
      const next = new Set(prev);
      if (next.has(column)) {
        next.delete(column);
      } else {
        next.add(column);
      }
      return next;
    });
  };

  const showAllColumns = () => {
    setHiddenColumns(new Set());
  };

  return {
    visibleColumns,
    visibleRows: sortedRows,
    sortState,
    setSortState,
    filters,
    setFilter,
    clearFilter,
    clearAllFilters,
    hiddenColumns,
    toggleHideColumn,
    showAllColumns,
  };
}
