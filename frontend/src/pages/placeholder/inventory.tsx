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

export function InventoryProductsPage() { return <ComingSoon titleKey="nav.inventory.products" />; }
export function StockBalancesPage()     { return <ComingSoon titleKey="nav.inventory.balances" />; }
export function MovementsPage()         { return <ComingSoon titleKey="nav.inventory.movements" />; }
export function TransfersPage()         { return <ComingSoon titleKey="nav.inventory.transfers" />; }
export function BatchesPage()           { return <ComingSoon titleKey="nav.inventory.batches" />; }
