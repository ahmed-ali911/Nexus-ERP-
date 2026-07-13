import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate } from "react-router-dom";
import axios from "axios";
import { AppButton, AppCard, AppForm, AppFormInput } from "@/components/ui";
import { useAppTheme, paletteTokens } from "@/theme";
import { useAuth, type AuthUser } from "@/contexts/AuthContext";
import { useLogin } from "@/api";
import type { BackendUser } from "@/api";

function mapToAuthUser(u: BackendUser): AuthUser {
  return {
    id: u.id,
    username: u.username,
    email: u.email,
    companyId: u.company_id,
    fullNameEn: u.full_name_en,
    fullNameAr: u.full_name_ar,
    isSuperuser: u.is_superuser,
    roles: [],
    permissions: u.is_superuser ? ["*"] : [],
  };
}

function mapError(err: unknown, t: (k: string) => string): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) return t("login.error.network");
    const detail = (err.response.data?.detail as string) ?? "";
    if (err.response.status === 401) {
      if (detail.toLowerCase().includes("locked")) return t("login.error.locked");
      if (detail.toLowerCase().includes("inactive")) return t("login.error.inactive");
      return t("login.error.invalidCredentials");
    }
  }
  return t("login.error.unknown");
}

type LoginForm = {
  companyCode: string;
  username: string;
  password: string;
};

export function LoginPage() {
  const { t } = useTranslation();
  const { palette, mode, direction } = useAppTheme();
  const tk = paletteTokens[palette][mode];
  const isRtl = direction === "rtl";

  const { isAuthenticated, setAuth } = useAuth();
  const navigate = useNavigate();
  const loginMutation = useLogin();
  const [serverError, setServerError] = useState<string | null>(null);

  // All hooks must be called before any conditional returns
  const schema = z.object({
    companyCode: z.string().min(1, t("login.validation.companyCode")),
    username:    z.string().min(1, t("login.validation.username")),
    password:    z.string().min(1, t("login.validation.password")),
  });

  const methods = useForm<LoginForm>({
    resolver: zodResolver(schema),
    defaultValues: { companyCode: "", username: "", password: "" },
  });

  // Already logged in — skip the login screen
  if (isAuthenticated) {
    return <Navigate to="/app/dashboard" replace />;
  }

  const handleSubmit = (data: LoginForm) => {
    setServerError(null);
    loginMutation.mutate(
      { company_code: data.companyCode.trim().toUpperCase(), username: data.username.trim(), password: data.password },
      {
        onSuccess: ({ tokens, user }) => {
          setAuth(mapToAuthUser(user), tokens.access_token, tokens.refresh_token);
          navigate("/app/dashboard", { replace: true });
        },
        onError: (err) => {
          setServerError(mapError(err, t));
        },
      }
    );
  };

  // ── Styles ────────────────────────────────────────────────────────────────

  const containerStyle: React.CSSProperties = {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: tk.background,
    padding: "1rem",
    direction: direction,
  };

  const cardMaxWidth = 400;

  const logoMarkStyle: React.CSSProperties = {
    width: 44,
    height: 44,
    borderRadius: 10,
    background: tk.primary,
    color: tk.textInverse,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: 800,
    fontSize: "1.25rem",
    letterSpacing: "-0.03em",
    flexShrink: 0,
    marginBottom: "0.875rem",
  };

  const appTitleStyle: React.CSSProperties = {
    margin: 0,
    fontSize: "1.375rem",
    fontWeight: 700,
    color: tk.textPrimary,
    letterSpacing: "-0.02em",
    lineHeight: 1.25,
  };

  const subtitleStyle: React.CSSProperties = {
    margin: "0.25rem 0 0",
    fontSize: "0.875rem",
    color: tk.textSecondary,
  };

  const dividerStyle: React.CSSProperties = {
    border: "none",
    borderTop: `1px solid ${tk.border}`,
    margin: "1.5rem 0",
  };

  const errorBoxStyle: React.CSSProperties = {
    padding: "0.75rem 1rem",
    background: tk.errorLight,
    color: tk.error,
    borderRadius: 6,
    fontSize: "0.8125rem",
    lineHeight: 1.5,
    border: `1px solid ${tk.error}22`,
  };

  const footerStyle: React.CSSProperties = {
    marginTop: "1.25rem",
    textAlign: "center" as const,
    fontSize: "0.6875rem",
    color: tk.textTertiary,
  };

  return (
    <div style={containerStyle}>
      <AppCard sx={{ width: "100%", maxWidth: cardMaxWidth }} padding={3}>
        {/* ── Brand area ────────────────────────────────────────────────── */}
        <div style={{ marginBottom: "0.25rem" }}>
          <div style={logoMarkStyle}>N</div>
          <h1 style={appTitleStyle}>{t("login.title")}</h1>
          <p style={subtitleStyle}>{t("login.subtitle")}</p>
        </div>

        <hr style={dividerStyle} />

        {/* ── Login form ────────────────────────────────────────────────── */}
        <AppForm methods={methods} onSubmit={handleSubmit} gap={2.5}>
          <AppFormInput
            name="companyCode"
            label={t("login.companyCode")}
            placeholder={isRtl ? "مثال: SL" : "e.g. SL"}
            autoComplete="organization"
          />

          <AppFormInput
            name="username"
            label={t("login.username")}
            autoComplete="username"
            autoFocus
          />

          <AppFormInput
            name="password"
            label={t("login.password")}
            type="password"
            autoComplete="current-password"
          />

          {serverError && (
            <div role="alert" style={errorBoxStyle}>
              {serverError}
            </div>
          )}

          <AppButton
            type="submit"
            appVariant="primary"
            fullWidth
            loading={loginMutation.isPending}
            sx={{ mt: 0.5 }}
          >
            {loginMutation.isPending ? t("login.loading") : t("login.submit")}
          </AppButton>
        </AppForm>

        <p style={footerStyle}>Nexus ERP · Sham Land Trading</p>
      </AppCard>
    </div>
  );
}
