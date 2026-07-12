import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useHealth } from "@/api";
import { useAppTheme, paletteTokens } from "@/theme";
import {
  AppButton,
  AppCard,
  AppInput,
  AppPage,
  AppSpinner,
  AppDialog,
} from "@/components/ui";
import { useToast } from "@/contexts/ToastContext";
import { Can } from "@/routes/Can";
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Divider from "@mui/material/Divider";

// NOTE: Box/Grid/Typography/Chip/Stack/Divider are MUI primitives used here as a
// TEMPORARY exception in the demo page only — they will be wrapped as App Components
// before any real screen uses them. See FRONTEND.md § App Component Rule.

export default function FoundationDemo() {
  const { t, i18n } = useTranslation();
  const { mode, palette, toggleMode, direction, setPalette } = useAppTheme();
  const health = useHealth();
  const toast = useToast();
  const [inputVal, setInputVal] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);

  const switchLang = (lang: string) => i18n.changeLanguage(lang);

  return (
    <AppPage
      title={t("demo.title")}
      subtitle={t("demo.subtitle")}
      breadcrumbs={[{ label: "Sham ERP" }, { label: t("demo.title") }]}
      actions={
        <Stack direction="row" spacing={1}>
          <AppButton
            appVariant={i18n.language === "ar" ? "primary" : "secondary"}
            onClick={() => switchLang("ar")}
            size="small"
          >
            العربية
          </AppButton>
          <AppButton
            appVariant={i18n.language === "en" ? "primary" : "secondary"}
            onClick={() => switchLang("en")}
            size="small"
          >
            English
          </AppButton>
          <AppButton
            appVariant={palette === "ocean" ? "primary" : "secondary"}
            onClick={() => setPalette("ocean")}
            size="small"
          >
            Ocean
          </AppButton>
          <AppButton
            appVariant={palette === "forest" ? "primary" : "secondary"}
            onClick={() => setPalette("forest")}
            size="small"
          >
            Forest
          </AppButton>
          <AppButton appVariant="text" onClick={toggleMode} size="small">
            {mode === "light" ? "🌙" : "☀️"}
          </AppButton>
        </Stack>
      }
    >
      <Grid container spacing={3}>
        {/* Status chips */}
        <Grid size={12}>
          <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
            <Chip
              label={`${t("demo.directionLabel")}: ${direction}`}
              size="small"
              color="primary"
              variant="outlined"
            />
            <Chip
              label={`${t("demo.modeLabel")}: ${mode}`}
              size="small"
              color="secondary"
              variant="outlined"
            />
            <Chip
              label={`Palette: ${palette}`}
              size="small"
              color="info"
              variant="outlined"
            />
            <Chip
              label={`Lang: ${i18n.language}`}
              size="small"
              variant="outlined"
            />
          </Stack>
        </Grid>

        {/* API / Health Check */}
        <Grid size={{ xs: 12, md: 4 }}>
          <AppCard title={t("health.title")}>
            {health.isLoading && <AppSpinner message={t("health.checking")} />}
            {health.isSuccess && (
              <Stack spacing={1}>
                <Chip
                  label={`status: ${health.data.status}`}
                  color="success"
                  sx={{ fontFamily: "monospace" }}
                />
                <Typography variant="body2" color="text.secondary">
                  {t("health.ok")}
                </Typography>
              </Stack>
            )}
            {health.isError && (
              <Stack spacing={1}>
                <Chip label="unreachable" color="error" />
                <Typography variant="body2" color="text.secondary">
                  {t("health.error")}
                </Typography>
                <AppButton
                  appVariant="secondary"
                  size="small"
                  onClick={() => health.refetch()}
                >
                  {t("common.retry")}
                </AppButton>
              </Stack>
            )}
          </AppCard>
        </Grid>

        {/* Button variants */}
        <Grid size={{ xs: 12, md: 4 }}>
          <AppCard title={t("demo.buttonVariants")}>
            <Stack spacing={1.5}>
              <AppButton appVariant="primary" fullWidth onClick={() => toast.success("Primary action!")}>
                Primary
              </AppButton>
              <AppButton appVariant="secondary" fullWidth onClick={() => toast.info("Secondary action")}>
                Secondary
              </AppButton>
              <AppButton appVariant="text" fullWidth onClick={() => toast.warning("Text action")}>
                Text
              </AppButton>
              <AppButton appVariant="danger" fullWidth onClick={() => setDialogOpen(true)}>
                Danger &rarr; Dialog
              </AppButton>
              <AppButton appVariant="primary" fullWidth loading>
                Loading&hellip;
              </AppButton>
            </Stack>
          </AppCard>
        </Grid>

        {/* Input + RBAC Can example */}
        <Grid size={{ xs: 12, md: 4 }}>
          <AppCard title={t("demo.inputExample")}>
            <Stack spacing={2}>
              <AppInput
                label={t("demo.inputLabel")}
                placeholder={t("demo.inputPlaceholder")}
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
              />
              {inputVal && (
                <Typography variant="body2" color="text.secondary">
                  Value: <strong>{inputVal}</strong>
                </Typography>
              )}
              <Divider />
              <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                RBAC: &lt;Can permission=&quot;demo.view&quot;&gt;
              </Typography>
              <Can permission="demo.view" fallback={
                <Typography variant="body2" color="text.secondary">
                  (no permission — hidden)
                </Typography>
              }>
                <AppButton appVariant="secondary" size="small" fullWidth>
                  Visible with demo.view
                </AppButton>
              </Can>
              <Can permission="*">
                <AppButton appVariant="primary" size="small" fullWidth>
                  Visible with wildcard *
                </AppButton>
              </Can>
            </Stack>
          </AppCard>
        </Grid>

        {/* Token swatch */}
        <Grid size={12}>
          <AppCard title={t("demo.tokens")} subtitle={`${palette} · ${mode} — live semantic tokens`}>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
              {((() => {
                const tk = paletteTokens[palette][mode];
                return [
                  ["primary", tk.primary],
                  ["secondary", tk.secondary],
                  ["success", tk.success],
                  ["warning", tk.warning],
                  ["error", tk.error],
                  ["info", tk.info],
                  ["background", tk.background],
                  ["surface", tk.surface],
                  ["border", tk.border],
                  ["sidebarBg", tk.sidebarBg],
                  ["sidebarIndicator", tk.sidebarActiveIndicator],
                ] as [string, string][];
              })()).map(([name, hex]) => (
                <Box
                  key={name}
                  sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.5 }}
                >
                  <Box
                    sx={{
                      width: 20,
                      height: 20,
                      borderRadius: 0.75,
                      bgcolor: hex,
                      border: "1px solid",
                      borderColor: "divider",
                      flexShrink: 0,
                    }}
                  />
                  <Typography variant="caption" sx={{ fontFamily: "monospace" }}>
                    {name}
                  </Typography>
                </Box>
              ))}
            </Box>
          </AppCard>
        </Grid>
      </Grid>

      {/* Confirm dialog */}
      <AppDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title="Confirm action"
        message="This is a confirmation dialog. It is built entirely from AppDialog — no direct MUI Dialog import in this page."
        onConfirm={() => {
          toast.success("Confirmed!");
          setDialogOpen(false);
        }}
        confirmLabel="Yes, proceed"
        cancelLabel={t("common.cancel")}
        danger
      />
    </AppPage>
  );
}
