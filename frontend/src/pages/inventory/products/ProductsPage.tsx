import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { AppPage, AppButton, AppInput, AppTable, AppChip, AppDialog } from "@/components/ui";
import type { TableColumn, RowAction } from "@/components/ui";
import { Can } from "@/routes/Can";
import {
  useProducts,
  useDeleteProduct,
  type ProductResponse,
} from "@/api/hooks/useProducts";
import { useCategories } from "@/api/hooks/useCategories";
import { useUnits } from "@/api/hooks/useUnits";
import { useToast } from "@/contexts/ToastContext";
import { ProductFormDialog } from "./ProductFormDialog";

// ── Component ──────────────────────────────────────────────────────────────────

export function ProductsPage() {
  const { t, i18n } = useTranslation();
  const toast = useToast();
  const isAr = i18n.language === "ar";

  const { data: products = [], isLoading, isError } = useProducts();
  const { data: categories = [] } = useCategories();
  const { data: units = [] } = useUnits();
  const deleteProduct = useDeleteProduct();

  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ProductResponse | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProductResponse | null>(null);

  const categoryMap = useMemo(
    () => new Map(categories.map((c) => [c.id, isAr ? c.name_ar : c.name_en])),
    [categories, isAr]
  );
  const unitMap = useMemo(
    () => new Map(units.map((u) => [u.id, u.symbol])),
    [units]
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return products;
    return products.filter(
      (p) =>
        p.code.toLowerCase().includes(q) ||
        p.name_en.toLowerCase().includes(q) ||
        p.name_ar.includes(q)
    );
  }, [products, search]);

  const columns: TableColumn<ProductResponse>[] = [
    {
      key: "code",
      header: t("products.columns.code"),
      sortable: true,
      getValue: (r) => r.code,
      render: (r) => (
        <span style={{ fontWeight: 600, fontFamily: "monospace" }}>{r.code}</span>
      ),
      width: 120,
    },
    {
      key: "name",
      header: t("products.columns.name"),
      sortable: true,
      getValue: (r) => (isAr ? r.name_ar : r.name_en),
      render: (r) => (
        <span>
          <span style={{ display: "block", fontWeight: 500 }}>
            {isAr ? r.name_ar : r.name_en}
          </span>
          <span style={{ display: "block", fontSize: "0.75rem", opacity: 0.6 }}>
            {isAr ? r.name_en : r.name_ar}
          </span>
        </span>
      ),
    },
    {
      key: "category",
      header: t("products.columns.category"),
      sortable: true,
      getValue: (r) => categoryMap.get(r.category_id) ?? "",
      render: (r) => categoryMap.get(r.category_id) ?? "—",
    },
    {
      key: "type",
      header: t("products.columns.type"),
      render: (r) => (
        <AppChip
          label={t(`products.type.${r.product_type}`)}
          color={
            r.product_type === "FINISHED_GOOD"
              ? "primary"
              : r.product_type === "SEMI_FINISHED"
              ? "warning"
              : "default"
          }
        />
      ),
      width: 140,
    },
    {
      key: "unit",
      header: t("products.columns.unit"),
      render: (r) => unitMap.get(r.base_unit_id) ?? "—",
      width: 80,
      align: "center",
    },
    {
      key: "status",
      header: t("products.columns.status"),
      render: (r) => (
        <span style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
          <AppChip
            label={r.is_active ? t("products.flags.active") : t("products.flags.inactive")}
            color={r.is_active ? "success" : "error"}
          />
          {r.is_sellable && (
            <AppChip label={t("products.flags.sellable")} color="primary" />
          )}
          {r.is_batch_tracked && (
            <AppChip label={t("products.flags.batchTracked")} color="warning" />
          )}
        </span>
      ),
    },
  ];

  const rowActions: RowAction<ProductResponse>[] = [
    {
      label: t("common.edit"),
      icon: "edit",
      onClick: (row) => {
        setEditing(row);
        setFormOpen(true);
      },
    },
    {
      label: t("common.delete"),
      icon: "delete",
      onClick: (row) => setDeleteTarget(row),
    },
  ];

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteProduct.mutateAsync(deleteTarget.id);
      toast.success(t("products.delete.success"));
    } catch {
      toast.error(t("products.error.delete"));
    } finally {
      setDeleteTarget(null);
    }
  };

  const handleNewProduct = () => {
    setEditing(null);
    setFormOpen(true);
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setEditing(null);
  };

  return (
    <AppPage
      title={t("nav.inventory.products")}
      breadcrumbs={[
        { label: t("nav.section.inventory") },
        { label: t("nav.inventory.products") },
      ]}
      actions={
        <Can permission="master_data.product.create">
          <AppButton appVariant="primary" onClick={handleNewProduct}>
            {t("products.newProduct")}
          </AppButton>
        </Can>
      }
    >
      <div style={{ marginBottom: "16px", maxWidth: "400px" }}>
        <AppInput
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("products.searchPlaceholder")}
          fullWidth
        />
      </div>

      <AppTable
        columns={columns}
        rows={filtered}
        rowKey={(r) => r.id}
        loading={isLoading}
        error={isError ? t("products.error.load") : null}
        empty={t("products.empty")}
        rowActions={rowActions}
      />

      <ProductFormDialog
        open={formOpen}
        onClose={handleFormClose}
        editing={editing}
      />

      <AppDialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title={t("products.delete.title")}
        message={t("products.delete.message", { code: deleteTarget?.code ?? "" })}
        onConfirm={handleDeleteConfirm}
        confirmLabel={t("products.delete.confirm")}
        cancelLabel={t("common.cancel")}
        loading={deleteProduct.isPending}
        danger
      />
    </AppPage>
  );
}
