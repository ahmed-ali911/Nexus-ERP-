import Box from "@mui/material/Box";
import { useAppTheme, paletteTokens } from "@/theme";

export type AppChipColor = "primary" | "success" | "warning" | "error" | "default";

export interface AppChipProps {
  label: string;
  color?: AppChipColor;
}

export function AppChip({ label, color = "default" }: AppChipProps) {
  const { palette, mode } = useAppTheme();
  const tk = paletteTokens[palette][mode];

  const colorMap: Record<AppChipColor, { bg: string; text: string }> = {
    primary: { bg: tk.primaryLight, text: tk.primary },
    success: { bg: mode === "dark" ? "#1b3a2a" : "#e8f5e9", text: mode === "dark" ? "#69f0ae" : "#2e7d32" },
    warning: { bg: mode === "dark" ? "#3a2a0a" : "#fff3e0", text: mode === "dark" ? "#ffcc02" : "#e65100" },
    error:   { bg: tk.errorLight,   text: tk.error },
    default: { bg: tk.background,   text: tk.textSecondary },
  };

  const { bg, text } = colorMap[color];

  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        px: 1,
        py: 0.25,
        borderRadius: "4px",
        fontSize: "0.6875rem",
        fontWeight: 600,
        bgcolor: bg,
        color: text,
        lineHeight: 1.5,
        border: `1px solid ${text}33`,
        whiteSpace: "nowrap",
        letterSpacing: "0.02em",
      }}
    >
      {label}
    </Box>
  );
}
