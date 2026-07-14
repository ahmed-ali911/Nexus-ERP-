import { useTranslation } from "react-i18next";
import { AppPage } from "@/components/ui";

function ComingSoon({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation();
  return (
    <AppPage title={t(titleKey)}>
      <p style={{ opacity: 0.6, fontSize: "0.9375rem" }}>{t("placeholder.comingSoon")}</p>
    </AppPage>
  );
}

export function PurchaseOrdersPage()   { return <ComingSoon titleKey="nav.purchasing.orders" />; }
export function GoodsReceiptsPage()    { return <ComingSoon titleKey="nav.purchasing.receipts" />; }
export function SupplierInvoicesPage() { return <ComingSoon titleKey="nav.purchasing.invoices" />; }
export function PurchasingPaymentsPage() { return <ComingSoon titleKey="nav.purchasing.payments" />; }
export function SuppliersPage()        { return <ComingSoon titleKey="nav.purchasing.suppliers" />; }
