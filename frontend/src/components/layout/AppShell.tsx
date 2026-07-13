import { Outlet } from "react-router-dom";
import Box from "@mui/material/Box";
import Drawer from "@mui/material/Drawer";
import { useAppTheme, paletteTokens } from "@/theme";
import { ShellProvider, useShell } from "./ShellContext";
import { AppSidebar } from "./AppSidebar";
import { AppHeader } from "./AppHeader";
import { HEADER_HEIGHT, SIDEBAR_WIDTH, RAIL_WIDTH } from "./navConfig";

function AppShellInner() {
  const { palette, mode, direction } = useAppTheme();
  const tk = paletteTokens[palette][mode];
  const { collapsed, mobileOpen, setMobileOpen } = useShell();
  const isRtl = direction === "rtl";
  const sidebarWidth = collapsed ? RAIL_WIDTH : SIDEBAR_WIDTH;

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      {/* ── Fixed header (full width, above everything) ───────────────────── */}
      <AppHeader />

      {/* ── Desktop sidebar — fixed, below header ─────────────────────────── */}
      <Box
        component="nav"
        sx={{
          position: "fixed",
          top: HEADER_HEIGHT,
          bottom: 0,
          ...(isRtl ? { right: 0 } : { left: 0 }),
          width: sidebarWidth,
          display: { xs: "none", md: "flex" },
          flexDirection: "column",
          bgcolor: tk.sidebarBg,
          zIndex: 1000,
          transition: "width 0.2s ease",
          overflowX: "hidden",
        }}
      >
        <AppSidebar compact={collapsed} />
      </Box>

      {/* ── Mobile drawer ─────────────────────────────────────────────────── */}
      <Drawer
        variant="temporary"
        anchor={isRtl ? "right" : "left"}
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: "block", md: "none" },
          "& .MuiDrawer-paper": {
            width: SIDEBAR_WIDTH,
            bgcolor: tk.sidebarBg,
            border: "none",
          },
        }}
      >
        {/* Give the mobile drawer a top spacer so content clears the header */}
        <Box sx={{ height: HEADER_HEIGHT, flexShrink: 0, bgcolor: tk.sidebarBg }} />
        <Box sx={{ flex: 1, overflow: "hidden" }}>
          <AppSidebar compact={false} />
        </Box>
      </Drawer>

      {/* ── Scrollable content area ───────────────────────────────────────── */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          mt: `${HEADER_HEIGHT}px`,
          ...(isRtl
            ? { mr: { md: `${sidebarWidth}px` }, ml: 0 }
            : { ml: { md: `${sidebarWidth}px` }, mr: 0 }),
          transition: "margin 0.2s ease",
          minHeight: `calc(100vh - ${HEADER_HEIGHT}px)`,
          bgcolor: tk.background,
          overflow: "auto",
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
}

/** Top-level shell wrapper — provides ShellContext and renders the layout. */
export function AppShell() {
  return (
    <ShellProvider>
      <AppShellInner />
    </ShellProvider>
  );
}
