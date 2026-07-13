import { useTranslation } from "react-i18next";
import { AppPage } from "@/components/ui";

export function AccountingPage() {
  const { t } = useTranslation();
  return (
    <AppPage title={t("nav.accounting")}>
      <p style={{ color: "var(--placeholder-text, inherit)", opacity: 0.6, fontSize: "0.9375rem" }}>
        {t("placeholder.comingSoon")}
      </p>
    </AppPage>
  );
}
