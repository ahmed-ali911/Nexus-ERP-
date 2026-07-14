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

export function ChartOfAccountsPage() { return <ComingSoon titleKey="nav.accounting.accounts" />; }
export function JournalEntriesPage()  { return <ComingSoon titleKey="nav.accounting.journal" />; }
export function TrialBalancePage()    { return <ComingSoon titleKey="nav.accounting.trialBalance" />; }
export function ProfitLossPage()      { return <ComingSoon titleKey="nav.accounting.pnl" />; }
export function BalanceSheetPage()    { return <ComingSoon titleKey="nav.accounting.balanceSheet" />; }
