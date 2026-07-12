import createCache from "@emotion/cache";
import { createTheme, type Theme } from "@mui/material/styles";
import { prefixer } from "stylis";
import rtlPlugin from "stylis-plugin-rtl";
import { paletteTokens, radiusTokens, typographyTokens, type ColorMode, type PaletteId } from "./tokens";
import type { Direction } from "@/i18n";

export { type Direction };

export function buildEmotionCache(direction: Direction) {
  return direction === "rtl"
    ? createCache({ key: "mui-rtl", stylisPlugins: [prefixer, rtlPlugin] })
    : createCache({ key: "mui-ltr" });
}

export function buildMuiTheme(palette: PaletteId, mode: ColorMode, direction: Direction): Theme {
  const t = paletteTokens[palette][mode];
  const isAr = direction === "rtl";

  return createTheme({
    direction,
    palette: {
      mode,
      primary:    { main: t.primary,  light: t.primaryLight,   dark: t.primaryActive  },
      secondary:  { main: t.secondary, light: t.secondaryLight, dark: t.secondaryActive },
      success:    { main: t.success,   light: t.successLight },
      warning:    { main: t.warning,   light: t.warningLight },
      error:      { main: t.error,     light: t.errorLight },
      info:       { main: t.info,      light: t.infoLight },
      background: { default: t.background, paper: t.surface },
      text:       { primary: t.textPrimary, secondary: t.textSecondary, disabled: t.textDisabled },
      divider: t.border,
    },
    shape: { borderRadius: radiusTokens.lg },
    typography: {
      fontFamily: isAr ? typographyTokens.fontFamilyAr : typographyTokens.fontFamilyEn,
      fontSize: 14,
      fontWeightRegular: typographyTokens.fontWeightRegular,
      fontWeightMedium:  typographyTokens.fontWeightMedium,
      fontWeightBold:    typographyTokens.fontWeightBold,
      h1: { fontSize: typographyTokens.size["3xl"], fontWeight: typographyTokens.fontWeightBold },
      h2: { fontSize: typographyTokens.size["2xl"], fontWeight: typographyTokens.fontWeightBold },
      h3: { fontSize: typographyTokens.size.xl,    fontWeight: typographyTokens.fontWeightSemibold },
      h4: { fontSize: typographyTokens.size.lg,    fontWeight: typographyTokens.fontWeightSemibold },
      h5: { fontSize: typographyTokens.size.md,    fontWeight: typographyTokens.fontWeightMedium },
      h6: { fontSize: typographyTokens.size.base,  fontWeight: typographyTokens.fontWeightMedium },
      body1: { fontSize: typographyTokens.size.base },
      body2: { fontSize: typographyTokens.size.sm },
      caption: { fontSize: typographyTokens.size.xs, letterSpacing: typographyTokens.letterSpacing.wide },
      button: { fontSize: typographyTokens.size.base, fontWeight: typographyTokens.fontWeightMedium, textTransform: "none" },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: radiusTokens.md,
            boxShadow: "none",
            "&:hover": { boxShadow: "none" },
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: radiusTokens.xl,
            boxShadow: t.shadowSm,
            border: `1px solid ${t.border}`,
          },
        },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            "& .MuiOutlinedInput-root": {
              borderRadius: radiusTokens.md,
              "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
                borderColor: t.borderFocus,
              },
            },
          },
        },
      },
      MuiSelect: {
        styleOverrides: {
          outlined: { borderRadius: radiusTokens.md },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
          },
        },
      },
      MuiDivider: {
        styleOverrides: {
          root: { borderColor: t.border },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { borderRadius: radiusTokens.sm },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: { borderRadius: radiusTokens["2xl"] },
        },
      },
    },
  });
}
