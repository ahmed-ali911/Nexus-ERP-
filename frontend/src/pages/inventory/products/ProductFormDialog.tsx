import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";
import {
  AppDialog,
  AppForm,
  AppFormInput,
  AppFormSelect,
  AppFormCheckbox,
} from "@/components/ui";
import {
  useCreateProduct,
  useUpdateProduct,
  type ProductResponse,
  type ProductCreate,
  type ProductType,
} from "@/api/hooks/useProducts";
import { useCategories } from "@/api/hooks/useCategories";
import { useUnits } from "@/api/hooks/useUnits";
import { useToast } from "@/contexts/ToastContext";

// ── Schema ─────────────────────────────────────────────────────────────────────

function buildSchema(t: (k: string) => string) {
  return z.object({
    code:             z.string().min(1, t("products.validation.code")),
    name_en:          z.string().min(1, t("products.validation.nameEn")),
    name_ar:          z.string().min(1, t("products.validation.nameAr")),
    category_id:      z.number().min(1, t("products.validation.category")),
    product_type:     z.enum(["RAW_MATERIAL", "SEMI_FINISHED", "FINISHED_GOOD"] as const, {
      error: t("products.validation.type"),
    }),
    base_unit_id:     z.number().min(1, t("products.validation.baseUnit")),
    barcode:          z.string().optional().nullable(),
    is_active:        z.boolean(),
    is_sellable:      z.boolean(),
    is_purchasable:   z.boolean(),
    is_stockable:     z.boolean(),
    is_batch_tracked: z.boolean(),
  });
}

type FormValues = z.infer<ReturnType<typeof buildSchema>>;

// ── Props ──────────────────────────────────────────────────────────────────────

interface ProductFormDialogProps {
  open: boolean;
  onClose: () => void;
  editing?: ProductResponse | null;
}

const EMPTY_DEFAULTS = {
  code:             "",
  name_en:          "",
  name_ar:          "",
  category_id:      0,
  product_type:     "RAW_MATERIAL" as const,
  base_unit_id:     0,
  barcode:          "",
  is_active:        true,
  is_sellable:      true,
  is_purchasable:   true,
  is_stockable:     true,
  is_batch_tracked: false,
};

// ── Component ──────────────────────────────────────────────────────────────────

export function ProductFormDialog({ open, onClose, editing }: ProductFormDialogProps) {
  const { t, i18n } = useTranslation();
  const toast = useToast();
  const isAr = i18n.language === "ar";

  const { data: categories = [] } = useCategories();
  const { data: units = [] } = useUnits();

  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct();

  const schema = buildSchema(t);

  const methods = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: EMPTY_DEFAULTS,
  });

  const isLoading = createProduct.isPending || updateProduct.isPending;

  useEffect(() => {
    if (editing) {
      methods.reset({
        code:             editing.code,
        name_en:          editing.name_en,
        name_ar:          editing.name_ar,
        category_id:      editing.category_id,
        product_type:     editing.product_type,
        base_unit_id:     editing.base_unit_id,
        barcode:          editing.barcode ?? "",
        is_active:        editing.is_active,
        is_sellable:      editing.is_sellable,
        is_purchasable:   editing.is_purchasable,
        is_stockable:     editing.is_stockable,
        is_batch_tracked: editing.is_batch_tracked,
      });
    } else {
      methods.reset(EMPTY_DEFAULTS);
    }
  }, [editing, open, methods]);

  const handleClose = () => {
    if (!isLoading) onClose();
  };

  const onSubmit = async (values: FormValues) => {
    const payload: ProductCreate = {
      ...values,
      barcode: values.barcode || null,
    };

    try {
      if (editing) {
        await updateProduct.mutateAsync({ id: editing.id, ...payload });
        toast.success(t("products.edit.success"));
      } else {
        await createProduct.mutateAsync(payload);
        toast.success(t("products.create.success"));
      }
      onClose();
    } catch {
      toast.error(t(editing ? "products.error.update" : "products.error.create"));
    }
  };

  const categoryOptions = categories
    .filter((c) => c.is_active && !c.is_deleted)
    .map((c) => ({ value: c.id, label: isAr ? c.name_ar : c.name_en }));

  const unitOptions = units
    .filter((u) => u.is_active && !u.is_deleted)
    .map((u) => ({ value: u.id, label: `${isAr ? u.name_ar : u.name_en} (${u.symbol})` }));

  const typeOptions: Array<{ value: ProductType; label: string }> = [
    { value: "RAW_MATERIAL",  label: t("products.type.RAW_MATERIAL") },
    { value: "SEMI_FINISHED", label: t("products.type.SEMI_FINISHED") },
    { value: "FINISHED_GOOD", label: t("products.type.FINISHED_GOOD") },
  ];

  const rowStyle: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: "16px" };
  const halfStyle: React.CSSProperties = { flex: "1 1 200px", minWidth: 0 };
  const thirdStyle: React.CSSProperties = { flex: "1 1 150px", minWidth: 0 };
  const flagsStyle: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: "4px" };
  const dividerStyle: React.CSSProperties = {
    border: "none",
    borderTop: "1px solid rgba(0,0,0,0.12)",
    margin: "0 0 12px 0",
  };

  return (
    <AppDialog
      open={open}
      onClose={handleClose}
      title={editing ? t("products.edit.title") : t("products.create.title")}
      confirmLabel={t("common.save")}
      cancelLabel={t("common.cancel")}
      loading={isLoading}
      onConfirm={methods.handleSubmit(onSubmit)}
    >
      <AppForm methods={methods} onSubmit={onSubmit} gap={2.5}>
        {/* Core identity */}
        <div style={rowStyle}>
          <div style={halfStyle}>
            <AppFormInput name="code" label={t("products.fields.code")} fullWidth disabled={isLoading} />
          </div>
          <div style={halfStyle}>
            <AppFormInput name="barcode" label={t("products.fields.barcode")} fullWidth disabled={isLoading} />
          </div>
          <div style={halfStyle}>
            <AppFormInput name="name_en" label={t("products.fields.nameEn")} fullWidth disabled={isLoading} />
          </div>
          <div style={halfStyle}>
            <AppFormInput name="name_ar" label={t("products.fields.nameAr")} fullWidth disabled={isLoading} />
          </div>
        </div>

        {/* Classification */}
        <div style={rowStyle}>
          <div style={thirdStyle}>
            <AppFormSelect name="category_id" label={t("products.fields.category")} options={categoryOptions} disabled={isLoading} fullWidth />
          </div>
          <div style={thirdStyle}>
            <AppFormSelect name="product_type" label={t("products.fields.type")} options={typeOptions} disabled={isLoading} fullWidth />
          </div>
          <div style={thirdStyle}>
            <AppFormSelect name="base_unit_id" label={t("products.fields.baseUnit")} options={unitOptions} disabled={isLoading} fullWidth />
          </div>
        </div>

        {/* Flags */}
        <div>
          <hr style={dividerStyle} />
          <div style={flagsStyle}>
            <AppFormCheckbox name="is_active"        label={t("products.fields.isActive")}       disabled={isLoading} />
            <AppFormCheckbox name="is_sellable"      label={t("products.fields.isSellable")}     disabled={isLoading} />
            <AppFormCheckbox name="is_purchasable"   label={t("products.fields.isPurchasable")}  disabled={isLoading} />
            <AppFormCheckbox name="is_stockable"     label={t("products.fields.isStockable")}    disabled={isLoading} />
            <AppFormCheckbox name="is_batch_tracked" label={t("products.fields.isBatchTracked")} disabled={isLoading} />
          </div>
        </div>
      </AppForm>
    </AppDialog>
  );
}
