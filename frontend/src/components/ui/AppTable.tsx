import { useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import Box from "@mui/material/Box";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TablePagination from "@mui/material/TablePagination";
import TableSortLabel from "@mui/material/TableSortLabel";
import Skeleton from "@mui/material/Skeleton";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import EditOutlinedIcon   from "@mui/icons-material/EditOutlined";
import DeleteOutlinedIcon from "@mui/icons-material/DeleteOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import InboxOutlinedIcon  from "@mui/icons-material/InboxOutlined";
import { useAppTheme, paletteTokens } from "@/theme";

// ── Column type ───────────────────────────────────────────────────────────────

type SortableColumn<T> = {
  sortable: true;
  getValue: (row: T) => string | number;
};
type NonSortableColumn = {
  sortable?: false;
  getValue?: undefined;
};

export type TableColumn<T> = {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  width?: string | number;
} & (SortableColumn<T> | NonSortableColumn);

// ── Row action ────────────────────────────────────────────────────────────────

export interface RowAction<T> {
  label: string;
  icon: "edit" | "delete" | "view";
  onClick: (row: T) => void;
  visible?: (row: T) => boolean;
  disabled?: (row: T) => boolean;
}

// ── Props ─────────────────────────────────────────────────────────────────────

export interface AppTableProps<T> {
  columns: TableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  loading?: boolean;
  error?: string | null;
  empty?: string;
  defaultPageSize?: number;
  rowActions?: RowAction<T>[];
}

// ── Component ─────────────────────────────────────────────────────────────────

const SKELETON_ROWS = 5;
const PAGE_SIZE_OPTIONS = [10, 25, 50] as const;

const ACTION_ICONS = {
  edit:   <EditOutlinedIcon fontSize="inherit" />,
  delete: <DeleteOutlinedIcon fontSize="inherit" />,
  view:   <VisibilityOutlinedIcon fontSize="inherit" />,
};

export function AppTable<T>({
  columns,
  rows,
  rowKey,
  loading = false,
  error = null,
  empty,
  defaultPageSize = 10,
  rowActions,
}: AppTableProps<T>) {
  const { t, i18n } = useTranslation();
  const { palette, mode, direction } = useAppTheme();
  const tk = paletteTokens[palette][mode];
  const isRtl = direction === "rtl";

  const [sortKey,  setSortKey]  = useState<string | null>(null);
  const [sortDir,  setSortDir]  = useState<"asc" | "desc">("asc");
  const [page,     setPage]     = useState(0);
  const [pageSize, setPageSize] = useState(defaultPageSize);

  const handleSortClick = (key: string) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  };

  // Sort
  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    const col = columns.find((c) => c.key === sortKey);
    if (!col?.sortable) return rows;
    return [...rows].sort((a, b) => {
      const va = (col as SortableColumn<T>).getValue(a);
      const vb = (col as SortableColumn<T>).getValue(b);
      const cmp =
        typeof va === "string" && typeof vb === "string"
          ? va.localeCompare(vb, i18n.language)
          : (va as number) - (vb as number);
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [rows, sortKey, sortDir, columns, i18n.language]);

  // Clamp page to valid range when filtered rows shrink (avoids empty page)
  const maxPage = sorted.length > 0 ? Math.ceil(sorted.length / pageSize) - 1 : 0;
  const effectivePage = Math.min(page, maxPage);

  // Paginate
  const paged = sorted.slice(effectivePage * pageSize, (effectivePage + 1) * pageSize);

  const hasActions = rowActions && rowActions.length > 0;
  const colCount = columns.length + (hasActions ? 1 : 0);

  const cellSx = {
    fontSize: "0.8125rem",
    borderColor: tk.border,
    color: tk.textPrimary,
  };

  const headCellSx = {
    ...cellSx,
    fontWeight: 700,
    bgcolor: tk.background,
    color: tk.textSecondary,
    fontSize: "0.75rem",
    letterSpacing: "0.04em",
    textTransform: "uppercase" as const,
    py: 1.25,
  };

  return (
    <Box>
      <TableContainer
        sx={{
          borderRadius: 2,
          border: `1px solid ${tk.border}`,
          bgcolor: tk.surface,
          overflowX: "auto",
        }}
      >
        <Table size="small" sx={{ minWidth: 480 }}>
          <TableHead>
            <TableRow>
              {columns.map((col) => (
                <TableCell
                  key={col.key}
                  align={col.align ?? (isRtl ? "right" : "left")}
                  width={col.width}
                  sx={headCellSx}
                >
                  {col.sortable ? (
                    <TableSortLabel
                      active={sortKey === col.key}
                      direction={sortKey === col.key ? sortDir : "asc"}
                      onClick={() => handleSortClick(col.key)}
                      sx={{
                        color: `${tk.textSecondary} !important`,
                        "& .MuiTableSortLabel-icon": { opacity: 0.4 },
                        "&.Mui-active": { color: `${tk.primary} !important` },
                        "&.Mui-active .MuiTableSortLabel-icon": { opacity: 1 },
                      }}
                    >
                      {col.header}
                    </TableSortLabel>
                  ) : (
                    col.header
                  )}
                </TableCell>
              ))}
              {hasActions && (
                <TableCell
                  align={isRtl ? "left" : "right"}
                  width={96}
                  sx={headCellSx}
                >
                  {t("common.actions")}
                </TableCell>
              )}
            </TableRow>
          </TableHead>

          <TableBody>
            {/* Loading skeleton */}
            {loading &&
              Array.from({ length: SKELETON_ROWS }).map((_, i) => (
                <TableRow key={i}>
                  {columns.map((col) => (
                    <TableCell key={col.key} sx={cellSx}>
                      <Skeleton height={18} />
                    </TableCell>
                  ))}
                  {hasActions && (
                    <TableCell sx={cellSx}>
                      <Skeleton height={18} width={60} />
                    </TableCell>
                  )}
                </TableRow>
              ))}

            {/* Error */}
            {!loading && error && (
              <TableRow>
                <TableCell colSpan={colCount} align="center" sx={{ py: 6, ...cellSx }}>
                  <Typography variant="body2" color="error">
                    {error}
                  </Typography>
                </TableCell>
              </TableRow>
            )}

            {/* Empty */}
            {!loading && !error && paged.length === 0 && (
              <TableRow>
                <TableCell colSpan={colCount} align="center" sx={{ py: 6, ...cellSx }}>
                  <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1, opacity: 0.5 }}>
                    <InboxOutlinedIcon sx={{ fontSize: "2rem" }} />
                    <Typography variant="body2">
                      {empty ?? t("common.noData")}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            )}

            {/* Data rows */}
            {!loading &&
              !error &&
              paged.map((row) => (
                <TableRow
                  key={rowKey(row)}
                  hover
                  sx={{
                    "&:last-child td": { borderBottom: "none" },
                    "&:hover": { bgcolor: tk.background },
                    transition: "background 0.1s",
                  }}
                >
                  {columns.map((col) => (
                    <TableCell
                      key={col.key}
                      align={col.align ?? (isRtl ? "right" : "left")}
                      sx={cellSx}
                    >
                      {col.render(row)}
                    </TableCell>
                  ))}
                  {hasActions && (
                    <TableCell align={isRtl ? "left" : "right"} sx={{ ...cellSx, py: 0.5 }}>
                      <Box sx={{ display: "flex", gap: 0.25, justifyContent: isRtl ? "flex-start" : "flex-end" }}>
                        {rowActions
                          .filter((a) => !a.visible || a.visible(row))
                          .map((action) => (
                            <Tooltip key={action.label} title={action.label}>
                              <span>
                                <IconButton
                                  size="small"
                                  onClick={() => action.onClick(row)}
                                  disabled={action.disabled?.(row)}
                                  sx={{
                                    color: action.icon === "delete" ? tk.error : tk.textSecondary,
                                    fontSize: "1rem",
                                    "&:hover": {
                                      color: action.icon === "delete" ? tk.error : tk.primary,
                                      bgcolor: action.icon === "delete" ? tk.errorLight : tk.primaryLight,
                                    },
                                  }}
                                >
                                  {ACTION_ICONS[action.icon]}
                                </IconButton>
                              </span>
                            </Tooltip>
                          ))}
                      </Box>
                    </TableCell>
                  )}
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination — only when there's actual data */}
      {!loading && !error && rows.length > 0 && (
        <TablePagination
          component="div"
          rowsPerPageOptions={[...PAGE_SIZE_OPTIONS]}
          count={sorted.length}
          rowsPerPage={pageSize}
          page={effectivePage}
          onPageChange={(_, p) => setPage(p)}
          onRowsPerPageChange={(e) => {
            setPageSize(Number(e.target.value));
            setPage(0);
          }}
          labelRowsPerPage={t("common.rowsPerPage")}
          labelDisplayedRows={({ from, to, count }) =>
            `${from}–${to} ${t("common.of")} ${count}`
          }
          sx={{
            borderTop: `1px solid ${tk.border}`,
            "& .MuiTablePagination-toolbar": { direction: "ltr" },
            color: tk.textSecondary,
            fontSize: "0.8125rem",
          }}
        />
      )}
    </Box>
  );
}
