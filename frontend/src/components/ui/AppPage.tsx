import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Breadcrumbs from "@mui/material/Breadcrumbs";
import Divider from "@mui/material/Divider";
import type { ReactNode } from "react";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface AppPageProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: ReactNode;
  children: ReactNode;
}

export function AppPage({
  title,
  subtitle,
  breadcrumbs,
  actions,
  children,
}: AppPageProps) {
  return (
    <Box
      component="main"
      sx={{
        p: { xs: 2, sm: 3 },
        maxWidth: 1280,
        mx: "auto",
        width: "100%",
      }}
    >
      {/* Breadcrumbs */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Breadcrumbs sx={{ mb: 1 }}>
          {breadcrumbs.map((b, i) => (
            <Typography
              key={i}
              variant="caption"
              color={i === breadcrumbs.length - 1 ? "text.primary" : "text.secondary"}
              sx={{ letterSpacing: "0.04em", textTransform: "uppercase" }}
            >
              {b.label}
            </Typography>
          ))}
        </Breadcrumbs>
      )}

      {/* Header */}
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          mb: 1.5,
        }}
      >
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {subtitle}
            </Typography>
          )}
        </Box>
        {actions && <Box sx={{ flexShrink: 0 }}>{actions}</Box>}
      </Box>

      <Divider sx={{ mb: 3 }} />

      {children}
    </Box>
  );
}
