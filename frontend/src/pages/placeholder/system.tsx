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

export function UsersRolesPage()    { return <ComingSoon titleKey="nav.system.users" />; }
export function OrganizationPage()  { return <ComingSoon titleKey="nav.system.organization" />; }
export function ApprovalsPage()     { return <ComingSoon titleKey="nav.system.approvals" />; }
export function SystemSettingsPage() { return <ComingSoon titleKey="nav.system.settings" />; }
