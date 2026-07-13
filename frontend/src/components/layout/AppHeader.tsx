import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import Badge from "@mui/material/Badge";
import Divider from "@mui/material/Divider";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Avatar from "@mui/material/Avatar";
import TextField from "@mui/material/TextField";
import Select, { type SelectChangeEvent } from "@mui/material/Select";
import Popover from "@mui/material/Popover";
import MenuIcon from "@mui/icons-material/Menu";
import MenuOpenIcon from "@mui/icons-material/MenuOpen";
import NotificationsNoneOutlinedIcon from "@mui/icons-material/NotificationsNoneOutlined";
import SearchIcon from "@mui/icons-material/Search";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import useMediaQuery from "@mui/material/useMediaQuery";
import { useTheme } from "@mui/material/styles";
import { useAppTheme, paletteTokens } from "@/theme";
import { useAuth } from "@/contexts/AuthContext";
import { useOrgScope } from "@/contexts/OrgContext";
import { useShell } from "./ShellContext";
import { HEADER_HEIGHT, ROUTE_LABEL_MAP } from "./navConfig";

// ── stub notifications ────────────────────────────────────────────────────────
const STUB_NOTIFICATIONS = [
  { id: 1, text: "GRN #42 awaiting approval", time: "2m ago" },
  { id: 2, text: "Invoice INV-2026-0081 overdue", time: "1h ago" },
  { id: 3, text: "Low stock: Flour (< 10 bags)", time: "3h ago" },
];

export function AppHeader() {
  const { t, i18n } = useTranslation();
  const { palette, mode, direction, toggleMode, setPalette } = useAppTheme();
  const tk = paletteTokens[palette][mode];
  const { user, clearAuth } = useAuth();
  const { activeCompany, activeBranch, branches, setActiveBranchId } = useOrgScope();
  const { collapsed, toggleCollapsed, setMobileOpen } = useShell();
  const location = useLocation();
  const navigate = useNavigate();
  const muiTheme = useTheme();
  const isMobile = useMediaQuery(muiTheme.breakpoints.down("md"));

  const [notifAnchor, setNotifAnchor]   = useState<null | HTMLElement>(null);
  const [userAnchor,  setUserAnchor]    = useState<null | HTMLElement>(null);
  const [searchOpen,  setSearchOpen]    = useState(false);

  const isRtl = direction === "rtl";

  // Breadcrumb derived from current route
  const routeLabelKey = Object.entries(ROUTE_LABEL_MAP).find(
    ([route]) => location.pathname.startsWith(route)
  )?.[1];
  const pageLabel = routeLabelKey ? t(routeLabelKey) : "";

  const handleLogout = () => {
    setUserAnchor(null);
    clearAuth();
    navigate("/login", { replace: true });
  };

  const handleBranchChange = (e: SelectChangeEvent<number>) => {
    setActiveBranchId(Number(e.target.value));
  };

  const displayName = user
    ? (i18n.language === "ar" ? user.fullNameAr : user.fullNameEn) || user.username
    : "";
  const userInitial = displayName?.[0]?.toUpperCase() ?? "?";
  const userName    = displayName;
  const userRole    = user?.isSuperuser
    ? (i18n.language === "ar" ? "مدير النظام" : "System Administrator")
    : (user?.roles?.[0] ?? "");

  return (
    <Box
      component="header"
      sx={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        height: HEADER_HEIGHT,
        zIndex: 1100,
        bgcolor: tk.surface,
        borderBottom: `1px solid ${tk.border}`,
        boxShadow: tk.shadowSm,
        display: "flex",
        alignItems: "center",
        px: 1.5,
        gap: 1,
      }}
    >
      {/* ── Start: hamburger / collapse + breadcrumb ──────────────────────── */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, flexShrink: 0 }}>
        {isMobile ? (
          <Tooltip title={t("shell.openMenu")}>
            <IconButton
              size="small"
              onClick={() => setMobileOpen(true)}
              sx={{ color: tk.textSecondary }}
            >
              <MenuIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : (
          <Tooltip title={collapsed ? t("shell.expandMenu") : t("shell.collapseMenu")}>
            <IconButton
              size="small"
              onClick={toggleCollapsed}
              sx={{ color: tk.textSecondary }}
            >
              {collapsed ? (
                <MenuIcon fontSize="small" />
              ) : (
                <MenuOpenIcon fontSize="small" sx={{ transform: isRtl ? "scaleX(-1)" : "none" }} />
              )}
            </IconButton>
          </Tooltip>
        )}

        {/* Breadcrumb */}
        {pageLabel && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            <Typography
              sx={{
                fontSize: "0.75rem",
                color: tk.textTertiary,
                display: { xs: "none", sm: "block" },
              }}
            >
              Nexus ERP
            </Typography>
            <Typography sx={{ fontSize: "0.75rem", color: tk.textTertiary, display: { xs: "none", sm: "block" } }}>
              /
            </Typography>
            <Typography
              sx={{
                fontSize: "0.8125rem",
                fontWeight: 600,
                color: tk.textPrimary,
                display: { xs: "none", sm: "block" },
              }}
            >
              {pageLabel}
            </Typography>
          </Box>
        )}
      </Box>

      {/* ── Spacer ────────────────────────────────────────────────────────── */}
      <Box sx={{ flex: 1 }} />

      {/* ── End: controls ─────────────────────────────────────────────────── */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, flexShrink: 0 }}>

        {/* Company label (non-interactive — single company) */}
        {activeCompany && (
          <Box
            sx={{
              display: { xs: "none", lg: "flex" },
              alignItems: "center",
              gap: 0.75,
              px: 1.25,
              py: 0.5,
              borderRadius: 1,
              bgcolor: tk.primaryLight,
              border: `1px solid ${tk.border}`,
            }}
          >
            <Typography sx={{ fontSize: "0.6875rem", fontWeight: 600, color: tk.textSecondary, letterSpacing: "0.06em", textTransform: "uppercase" }}>
              {t("shell.company")}
            </Typography>
            <Typography sx={{ fontSize: "0.8125rem", fontWeight: 600, color: tk.textPrimary }}>
              {i18n.language === "ar" ? activeCompany.nameAr : activeCompany.nameEn}
            </Typography>

            {/* Branch selector — only shown when more than one branch */}
            {branches.length > 1 && activeBranch && (
              <>
                <Typography sx={{ fontSize: "0.75rem", color: tk.textTertiary, mx: 0.25 }}>·</Typography>
                <Typography sx={{ fontSize: "0.6875rem", fontWeight: 600, color: tk.textSecondary, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                  {t("shell.branch")}
                </Typography>
                <Select
                  value={activeBranch.id}
                  onChange={handleBranchChange}
                  size="small"
                  variant="standard"
                  disableUnderline
                  sx={{
                    fontSize: "0.8125rem",
                    fontWeight: 600,
                    color: tk.textPrimary,
                    "& .MuiSelect-select": { py: 0, pr: "20px !important" },
                    "& .MuiSelect-icon": { color: tk.textSecondary },
                  }}
                >
                  {branches.map((b) => (
                    <MenuItem key={b.id} value={b.id}>
                      {i18n.language === "ar" ? b.nameAr : b.nameEn}
                    </MenuItem>
                  ))}
                </Select>
              </>
            )}
            {branches.length === 1 && activeBranch && (
              <>
                <Typography sx={{ fontSize: "0.75rem", color: tk.textTertiary, mx: 0.25 }}>·</Typography>
                <Typography sx={{ fontSize: "0.8125rem", color: tk.textPrimary }}>
                  {i18n.language === "ar" ? activeBranch.nameAr : activeBranch.nameEn}
                </Typography>
              </>
            )}
          </Box>
        )}

        {/* Search — expandable stub */}
        {searchOpen ? (
          <TextField
            size="small"
            placeholder={t("shell.search")}
            autoFocus
            onBlur={() => setSearchOpen(false)}
            sx={{
              width: 200,
              "& .MuiOutlinedInput-root": {
                fontSize: "0.8125rem",
                bgcolor: tk.background,
              },
            }}
            // stub: no backend wired yet
          />
        ) : (
          <Tooltip title={t("common.search")}>
            <IconButton size="small" onClick={() => setSearchOpen(true)} sx={{ color: tk.textSecondary }}>
              <SearchIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}

        {/* Notifications */}
        <Tooltip title={t("shell.notifications")}>
          <IconButton
            size="small"
            onClick={(e) => setNotifAnchor(e.currentTarget)}
            sx={{ color: tk.textSecondary }}
          >
            <Badge badgeContent={STUB_NOTIFICATIONS.length} color="error" max={9}>
              <NotificationsNoneOutlinedIcon fontSize="small" />
            </Badge>
          </IconButton>
        </Tooltip>

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5, borderColor: tk.border }} />

        {/* Language toggle */}
        <Tooltip title={t("nav.language")}>
          <IconButton
            size="small"
            onClick={() => i18n.changeLanguage(i18n.language === "ar" ? "en" : "ar")}
            sx={{
              color: tk.textSecondary,
              fontSize: "0.75rem",
              fontWeight: 700,
              width: 30,
              height: 30,
              borderRadius: 1,
              border: `1px solid ${tk.border}`,
            }}
          >
            {i18n.language === "ar" ? "EN" : "ع"}
          </IconButton>
        </Tooltip>

        {/* Palette toggle */}
        <Tooltip title={`${t("shell.palette.label")}: ${palette === "ocean" ? t("shell.palette.forest") : t("shell.palette.ocean")}`}>
          <IconButton
            size="small"
            onClick={() => setPalette(palette === "ocean" ? "forest" : "ocean")}
            sx={{
              color: tk.textSecondary,
              fontSize: "0.625rem",
              fontWeight: 700,
              width: 30,
              height: 30,
              borderRadius: 1,
              border: `1px solid ${tk.border}`,
              lineHeight: 1,
            }}
          >
            {palette === "ocean" ? "🌊" : "🌲"}
          </IconButton>
        </Tooltip>

        {/* Mode toggle */}
        <Tooltip title={mode === "light" ? t("nav.dark") : t("nav.light")}>
          <IconButton
            size="small"
            onClick={toggleMode}
            sx={{ color: tk.textSecondary }}
          >
            {mode === "light" ? (
              <DarkModeOutlinedIcon fontSize="small" />
            ) : (
              <LightModeOutlinedIcon fontSize="small" />
            )}
          </IconButton>
        </Tooltip>

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5, borderColor: tk.border }} />

        {/* User menu */}
        <Tooltip title={userName}>
          <IconButton
            size="small"
            onClick={(e) => setUserAnchor(e.currentTarget)}
            sx={{ p: 0.25 }}
          >
            <Avatar
              sx={{
                width: 30,
                height: 30,
                fontSize: "0.75rem",
                fontWeight: 700,
                bgcolor: tk.primary,
                color: tk.textInverse,
              }}
            >
              {userInitial}
            </Avatar>
          </IconButton>
        </Tooltip>
      </Box>

      {/* ── Notifications popover ─────────────────────────────────────────── */}
      <Popover
        open={Boolean(notifAnchor)}
        anchorEl={notifAnchor}
        onClose={() => setNotifAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: isRtl ? "left" : "right" }}
        transformOrigin={{ vertical: "top", horizontal: isRtl ? "left" : "right" }}
        slotProps={{
          paper: {
            sx: {
              width: 320,
              mt: 0.5,
              bgcolor: tk.surface,
              border: `1px solid ${tk.border}`,
              boxShadow: tk.shadowMd,
              borderRadius: 2,
            },
          },
        }}
      >
        <Box sx={{ px: 2, pt: 1.75, pb: 1, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Typography sx={{ fontWeight: 600, fontSize: "0.875rem", color: tk.textPrimary }}>
            {t("shell.notifications")}
          </Typography>
          <Typography
            sx={{ fontSize: "0.75rem", color: tk.secondary, cursor: "pointer", "&:hover": { opacity: 0.8 } }}
            onClick={() => setNotifAnchor(null)}
          >
            {t("shell.markAllRead")}
          </Typography>
        </Box>
        <Divider sx={{ borderColor: tk.border }} />
        {STUB_NOTIFICATIONS.map((n) => (
          <Box
            key={n.id}
            sx={{
              px: 2, py: 1.5,
              borderBottom: `1px solid ${tk.borderLight}`,
              "&:last-child": { borderBottom: "none" },
              "&:hover": { bgcolor: tk.background },
              cursor: "pointer",
            }}
          >
            <Typography sx={{ fontSize: "0.8125rem", color: tk.textPrimary, lineHeight: 1.4 }}>
              {n.text}
            </Typography>
            <Typography sx={{ fontSize: "0.6875rem", color: tk.textTertiary, mt: 0.25 }}>
              {n.time}
            </Typography>
          </Box>
        ))}
      </Popover>

      {/* ── User menu ─────────────────────────────────────────────────────── */}
      <Menu
        anchorEl={userAnchor}
        open={Boolean(userAnchor)}
        onClose={() => setUserAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: isRtl ? "left" : "right" }}
        transformOrigin={{ vertical: "top", horizontal: isRtl ? "left" : "right" }}
        slotProps={{
          paper: {
            sx: {
              mt: 0.5,
              minWidth: 200,
              bgcolor: tk.surface,
              border: `1px solid ${tk.border}`,
              boxShadow: tk.shadowMd,
              borderRadius: 2,
            },
          },
        }}
      >
        {/* User identity header */}
        <Box sx={{ px: 2, py: 1.5 }}>
          <Typography sx={{ fontWeight: 600, fontSize: "0.875rem", color: tk.textPrimary }}>
            {userName}
          </Typography>
          {userRole && (
            <Typography sx={{ fontSize: "0.6875rem", color: tk.textSecondary }}>
              {userRole}
            </Typography>
          )}
        </Box>
        <Divider sx={{ borderColor: tk.border }} />
        <MenuItem onClick={() => setUserAnchor(null)} sx={{ fontSize: "0.8125rem", color: tk.textPrimary }}>
          {t("shell.userMenu.profile")}
        </MenuItem>
        <MenuItem onClick={() => setUserAnchor(null)} sx={{ fontSize: "0.8125rem", color: tk.textPrimary }}>
          {t("shell.userMenu.preferences")}
        </MenuItem>
        <Divider sx={{ borderColor: tk.border }} />
        <MenuItem
          onClick={handleLogout}
          sx={{ fontSize: "0.8125rem", color: tk.error }}
        >
          {t("shell.userMenu.logout")}
        </MenuItem>
      </Menu>
    </Box>
  );
}
