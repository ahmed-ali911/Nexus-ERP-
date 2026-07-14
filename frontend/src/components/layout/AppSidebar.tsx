import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Tooltip from "@mui/material/Tooltip";
import Divider from "@mui/material/Divider";
import Collapse from "@mui/material/Collapse";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useAppTheme, paletteTokens } from "@/theme";
import { useAuth } from "@/contexts/AuthContext";
import { useOrgScope } from "@/contexts/OrgContext";
import { useShell } from "./ShellContext";
import { NAV_CONFIG } from "./navConfig";

export interface AppSidebarProps {
  compact?: boolean;
}

export function AppSidebar({ compact = false }: AppSidebarProps) {
  const { t, i18n } = useTranslation();
  const { palette, mode, direction } = useAppTheme();
  const tk = paletteTokens[palette][mode];
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { activeCompany } = useOrgScope();
  const { setMobileOpen, isSectionExpanded, toggleSection, expandSection } = useShell();

  const isRtl = direction === "rtl";

  const canSee = (permission?: string): boolean => {
    if (!permission) return true;
    return (
      (user?.permissions.includes(permission) ?? false) ||
      (user?.permissions.includes("*") ?? false)
    );
  };

  const isActive = (path: string) => location.pathname.startsWith(path);

  const handleNav = (path: string) => {
    navigate(path);
    setMobileOpen(false);
  };

  // Auto-expand the section containing the active route on navigation
  useEffect(() => {
    const activeSection = NAV_CONFIG.find((s) =>
      s.items.some((item) => location.pathname.startsWith(item.path)),
    );
    if (activeSection) {
      expandSection(activeSection.labelKey);
    }
  }, [location.pathname, expandSection]);

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        bgcolor: tk.sidebarBg,
        overflow: "hidden",
      }}
    >
      {/* ── Brand ────────────────────────────────────────────────────────── */}
      <Box
        sx={{
          px: compact ? 0 : 2.5,
          py: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: compact ? "center" : "flex-start",
          flexShrink: 0,
          minHeight: 56,
        }}
      >
        {compact ? (
          <Typography sx={{ color: "#fff", fontWeight: 800, fontSize: "1.125rem", letterSpacing: "-0.02em" }}>
            N
          </Typography>
        ) : (
          <Box>
            <Typography sx={{ color: "#fff", fontWeight: 700, fontSize: "1.0625rem", letterSpacing: "-0.02em", lineHeight: 1.2 }}>
              Nexus ERP
            </Typography>
            {activeCompany && (
              <Typography sx={{ color: tk.sidebarText, fontSize: "0.6875rem", mt: 0.25, lineHeight: 1.3, opacity: 0.85 }}>
                {i18n.language === "ar" ? activeCompany.nameAr : activeCompany.nameEn}
              </Typography>
            )}
          </Box>
        )}
      </Box>

      <Divider sx={{ borderColor: "rgba(255,255,255,0.08)", flexShrink: 0 }} />

      {/* ── Nav ──────────────────────────────────────────────────────────── */}
      <Box sx={{ flex: 1, overflowY: "auto", overflowX: "hidden", py: 0.5 }}>
        {NAV_CONFIG.map((section) => {
          const visibleItems = section.items.filter((item) => canSee(item.permission));
          if (visibleItems.length === 0) return null;

          const isOpen = isSectionExpanded(section.labelKey);

          return (
            <Box key={section.labelKey}>
              {/* Section header */}
              {compact ? (
                <Box sx={{ my: 0.75 }}>
                  <Divider sx={{ borderColor: "rgba(255,255,255,0.08)", mx: 1 }} />
                </Box>
              ) : (
                <Box
                  onClick={() => toggleSection(section.labelKey)}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    px: 2.5,
                    pt: 1.75,
                    pb: 0.5,
                    cursor: "pointer",
                    userSelect: "none",
                    "&:hover": { opacity: 0.85 },
                  }}
                >
                  <Typography
                    sx={{
                      fontSize: "0.625rem",
                      fontWeight: 700,
                      letterSpacing: "0.1em",
                      textTransform: "uppercase",
                      color: tk.sidebarText,
                      opacity: 0.5,
                    }}
                  >
                    {t(section.labelKey)}
                  </Typography>
                  {isOpen ? (
                    <ExpandLessIcon sx={{ fontSize: "0.875rem", color: tk.sidebarText, opacity: 0.4 }} />
                  ) : (
                    <ExpandMoreIcon sx={{ fontSize: "0.875rem", color: tk.sidebarText, opacity: 0.4 }} />
                  )}
                </Box>
              )}

              {/* Items — always shown in compact mode (no collapse); collapsed in expanded mode */}
              <Collapse in={compact || isOpen} timeout={150}>
                {visibleItems.map((item) => {
                  const active = isActive(item.path);

                  const itemEl = (
                    <Box
                      key={item.path}
                      onClick={() => handleNav(item.path)}
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: compact ? "center" : "flex-start",
                        gap: 1.5,
                        mx: 1,
                        px: compact ? 0 : 1.5,
                        py: 0.875,
                        borderRadius: 1.5,
                        cursor: "pointer",
                        position: "relative",
                        color: active ? tk.sidebarTextActive : tk.sidebarText,
                        bgcolor: active ? "rgba(255,255,255,0.09)" : "transparent",
                        "&:hover": {
                          bgcolor: tk.sidebarHover,
                          color: tk.sidebarTextActive,
                        },
                        transition: "background 0.13s, color 0.13s",
                      }}
                    >
                      {/* Active indicator bar */}
                      {active && (
                        <Box
                          sx={{
                            position: "absolute",
                            top: 5,
                            bottom: 5,
                            ...(isRtl ? { right: -8 } : { left: -8 }),
                            width: 3,
                            borderRadius: isRtl ? "2px 0 0 2px" : "0 2px 2px 0",
                            bgcolor: tk.sidebarActiveIndicator,
                          }}
                        />
                      )}

                      <item.Icon sx={{ fontSize: "1.125rem", flexShrink: 0, color: "inherit" }} />

                      {!compact && (
                        <Typography
                          sx={{
                            fontSize: "0.8125rem",
                            fontWeight: active ? 600 : 400,
                            lineHeight: 1.3,
                            flex: 1,
                            color: "inherit",
                          }}
                        >
                          {t(item.labelKey)}
                        </Typography>
                      )}
                    </Box>
                  );

                  return compact ? (
                    <Tooltip key={item.path} title={t(item.labelKey)} placement={isRtl ? "left" : "right"}>
                      {itemEl}
                    </Tooltip>
                  ) : (
                    <Box key={item.path}>{itemEl}</Box>
                  );
                })}
              </Collapse>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
