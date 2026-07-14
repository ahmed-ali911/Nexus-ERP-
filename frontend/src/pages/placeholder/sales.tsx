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

export function SalesInvoicesPage()  { return <ComingSoon titleKey="nav.sales.invoices" />; }
export function CollectionsPage()    { return <ComingSoon titleKey="nav.sales.collections" />; }
export function CreditNotesPage()    { return <ComingSoon titleKey="nav.sales.creditNotes" />; }
export function SalesCustomersPage() { return <ComingSoon titleKey="nav.sales.customers" />; }
export function PriceListsPage()     { return <ComingSoon titleKey="nav.sales.priceLists" />; }
