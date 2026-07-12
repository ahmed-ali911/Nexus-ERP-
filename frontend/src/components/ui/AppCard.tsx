import Card, { type CardProps } from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import type { ReactNode } from "react";

export interface AppCardProps extends Omit<CardProps, "title"> {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  padding?: number;
  children: ReactNode;
}

export function AppCard({
  title,
  subtitle,
  actions,
  padding = 3,
  children,
  sx,
  ...rest
}: AppCardProps) {
  return (
    <Card sx={{ ...sx }} {...rest}>
      <CardContent sx={{ p: padding, "&:last-child": { pb: padding } }}>
        {(title || actions) && (
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              mb: title ? 2 : 0,
            }}
          >
            <Box>
              {title && (
                <Typography variant="h6" sx={{ fontWeight: 600, lineHeight: 1.3 }}>
                  {title}
                </Typography>
              )}
              {subtitle && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                  {subtitle}
                </Typography>
              )}
            </Box>
            {actions && <Box sx={{ flexShrink: 0 }}>{actions}</Box>}
          </Box>
        )}
        {children}
      </CardContent>
    </Card>
  );
}
