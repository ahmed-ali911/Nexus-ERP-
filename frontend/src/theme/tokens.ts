/**
 * Design tokens — single source of truth for visual identity.
 *
 * Two palette identities: "ocean" (Prussian Blue + teal) and "forest" (Forest Green + Sunglow).
 * Adding a new palette = add one entry to paletteTokens. Zero component changes.
 * Components reference semantic tokens only (primary, surface, textPrimary, …).
 */

export type PaletteId = "ocean" | "forest";
export type ColorMode = "light" | "dark";

export interface ColorTokens {
  primary: string;
  primaryHover: string;
  primaryActive: string;
  primaryLight: string;
  secondary: string;
  secondaryHover: string;
  secondaryActive: string;
  secondaryLight: string;
  success: string;
  successHover: string;
  successLight: string;
  warning: string;
  warningHover: string;
  warningLight: string;
  error: string;
  errorHover: string;
  errorLight: string;
  info: string;
  infoLight: string;
  background: string;
  surface: string;
  surfaceRaised: string;
  overlay: string;
  border: string;
  borderLight: string;
  borderFocus: string;
  textPrimary: string;
  textSecondary: string;
  textTertiary: string;
  textDisabled: string;
  textInverse: string;
  textLink: string;
  sidebarBg: string;
  sidebarText: string;
  sidebarTextActive: string;
  sidebarActiveIndicator: string;
  sidebarHover: string;
  shadowSm: string;
  shadowMd: string;
  shadowLg: string;
}

export const paletteTokens: Record<PaletteId, Record<ColorMode, ColorTokens>> = {
  // ── OCEAN ──────────────────────────────────────────────────────────────────
  // Source: Prussian Blue #003659 · Blue Chill #0B99A7 · Puerto Rico #37C4AA
  //         Padua #B6E9C1 · Feta #EEFBEB
  ocean: {
    light: {
      primary:         "#003659",
      primaryHover:    "#002A47",
      primaryActive:   "#001D30",
      primaryLight:    "#E0EEF5",
      secondary:       "#0B99A7",
      secondaryHover:  "#097E8A",
      secondaryActive: "#07656F",
      secondaryLight:  "#DCF2F4",
      success:         "#1D8348",
      successHover:    "#186A3B",
      successLight:    "#E9F7EF",
      warning:         "#D97706",
      warningHover:    "#B45309",
      warningLight:    "#FEF3C7",
      error:           "#DC2626",
      errorHover:      "#B91C1C",
      errorLight:      "#FEE2E2",
      info:            "#0B99A7",
      infoLight:       "#DCF2F4",
      background:      "#EEF7F8",
      surface:         "#FFFFFF",
      surfaceRaised:   "#FFFFFF",
      overlay:         "rgba(0,54,89,0.40)",
      border:          "#B6D8E0",
      borderLight:     "#D5EBF0",
      borderFocus:     "#0B99A7",
      textPrimary:     "#001D30",
      textSecondary:   "#3A6070",
      textTertiary:    "#7A9FB0",
      textDisabled:    "#B0CDD8",
      textInverse:     "#FFFFFF",
      textLink:        "#0B99A7",
      sidebarBg:              "#003659",
      sidebarText:            "#7DBDD0",
      sidebarTextActive:      "#FFFFFF",
      sidebarActiveIndicator: "#37C4AA",
      sidebarHover:           "rgba(55,196,170,0.12)",
      shadowSm: "0 1px 3px rgba(0,54,89,0.10), 0 1px 2px rgba(0,54,89,0.06)",
      shadowMd: "0 4px 8px rgba(0,54,89,0.10), 0 2px 4px rgba(0,54,89,0.06)",
      shadowLg: "0 10px 24px rgba(0,54,89,0.12), 0 4px 8px rgba(0,54,89,0.08)",
    },
    dark: {
      // Puerto Rico (#37C4AA) becomes the primary interactive on deep ocean background
      primary:         "#37C4AA",
      primaryHover:    "#4DD0B8",
      primaryActive:   "#63DCC6",
      primaryLight:    "#002535",
      secondary:       "#0BBFCF",
      secondaryHover:  "#22CED8",
      secondaryActive: "#38DBE4",
      secondaryLight:  "#001520",
      success:         "#34D27A",
      successHover:    "#4DDE8E",
      successLight:    "#071A0E",
      warning:         "#FBB824",
      warningHover:    "#FFC73A",
      warningLight:    "#1A1200",
      error:           "#FF6B6B",
      errorHover:      "#FF8585",
      errorLight:      "#1A0808",
      info:            "#0BBFCF",
      infoLight:       "#001525",
      background:      "#001422",
      surface:         "#002035",
      surfaceRaised:   "#002D4A",
      overlay:         "rgba(0,0,0,0.70)",
      border:          "#0A3550",
      borderLight:     "#062840",
      borderFocus:     "#37C4AA",
      textPrimary:     "#D8EEF4",
      textSecondary:   "#6BAFC4",
      textTertiary:    "#3D7A90",
      textDisabled:    "#1E4A60",
      textInverse:     "#001422",
      textLink:        "#37C4AA",
      sidebarBg:              "#000D1A",
      sidebarText:            "#3A7A95",
      sidebarTextActive:      "#D8EEF4",
      sidebarActiveIndicator: "#37C4AA",
      sidebarHover:           "rgba(55,196,170,0.10)",
      shadowSm: "0 1px 3px rgba(0,0,0,0.40)",
      shadowMd: "0 4px 8px rgba(0,0,0,0.45)",
      shadowLg: "0 10px 24px rgba(0,0,0,0.55)",
    },
  },

  // ── FOREST ─────────────────────────────────────────────────────────────────
  // Source: Ebony #070F16 · Forest Green #22822E · Sunglow #FFCB2B (accent only)
  //         Khaki #F1E392 · Beige #F7F6E4
  // Sunglow used sparingly: sidebarActiveIndicator, warning semantic, dark-mode accent.
  // Never as large surface or background — bright yellow tires the eye on big areas.
  forest: {
    light: {
      primary:         "#22822E",
      primaryHover:    "#1A6B25",
      primaryActive:   "#13561B",
      primaryLight:    "#E8F5E9",
      secondary:       "#A37B0A",  // darkened Sunglow → amber-gold, readable on white
      secondaryHover:  "#876508",
      secondaryActive: "#6B5006",
      secondaryLight:  "#FDF5D6",
      success:         "#1A6B25",
      successHover:    "#13561B",
      successLight:    "#E8F5E9",
      warning:         "#B8860B",  // muted Sunglow gold — readable on light surfaces
      warningHover:    "#9A7009",
      warningLight:    "#FEF8D4",
      error:           "#C62828",
      errorHover:      "#A31F1F",
      errorLight:      "#FDEAEA",
      info:            "#2E7D5E",  // forest teal — bridges green & informational
      infoLight:       "#E8F5EF",
      background:      "#F5F4E8",  // warm Beige
      surface:         "#FFFFFF",
      surfaceRaised:   "#FFFEF8",
      overlay:         "rgba(7,15,22,0.45)",
      border:          "#C8C9A8",  // warm khaki-gray from the Khaki/Beige family
      borderLight:     "#E0E1C8",
      borderFocus:     "#22822E",
      textPrimary:     "#1A2B1A",  // very dark forest green-black
      textSecondary:   "#47614A",
      textTertiary:    "#87A08A",
      textDisabled:    "#C0CEC2",
      textInverse:     "#FFFFFF",
      textLink:        "#22822E",
      sidebarBg:              "#070F16",  // Ebony — night forest
      sidebarText:            "#6A9270",
      sidebarTextActive:      "#F1E8D0",  // warm cream text on Ebony
      sidebarActiveIndicator: "#FFCB2B",  // Sunglow: small indicator on dark sidebar — perfect use
      sidebarHover:           "rgba(255,203,43,0.08)",
      shadowSm: "0 1px 3px rgba(7,15,22,0.08), 0 1px 2px rgba(7,15,22,0.05)",
      shadowMd: "0 4px 8px rgba(7,15,22,0.10), 0 2px 4px rgba(7,15,22,0.06)",
      shadowLg: "0 10px 24px rgba(7,15,22,0.12), 0 4px 8px rgba(7,15,22,0.08)",
    },
    dark: {
      // Ebony background; Forest Green brightened for dark; amber-gold as secondary accent
      primary:         "#4EC85C",
      primaryHover:    "#65D570",
      primaryActive:   "#7CE086",
      primaryLight:    "#0D1E10",
      secondary:       "#D4A820",  // amber-gold (muted Sunglow — less harsh than pure yellow on buttons)
      secondaryHover:  "#E8BC28",
      secondaryActive: "#FFCB2B",
      secondaryLight:  "#1E1800",
      success:         "#5DD86C",
      successHover:    "#74E080",
      successLight:    "#0A1A0C",
      warning:         "#FFCB2B",  // full Sunglow as warning on dark Ebony — correct use of the color
      warningHover:    "#FFD952",
      warningLight:    "#1E1800",
      error:           "#FF6B6B",
      errorHover:      "#FF8585",
      errorLight:      "#1A0808",
      info:            "#5EC4A0",  // teal-green for info on dark
      infoLight:       "#0A1810",
      background:      "#070F16",  // Ebony
      surface:         "#0D1A10",  // very dark green-black
      surfaceRaised:   "#122015",
      overlay:         "rgba(0,0,0,0.75)",
      border:          "#1A3020",
      borderLight:     "#102018",
      borderFocus:     "#4EC85C",
      textPrimary:     "#EEF4E8",
      textSecondary:   "#8ABE92",
      textTertiary:    "#507858",
      textDisabled:    "#2A4430",
      textInverse:     "#070F16",
      textLink:        "#4EC85C",
      sidebarBg:              "#040B08",
      sidebarText:            "#4A7A52",
      sidebarTextActive:      "#EEF4E8",
      sidebarActiveIndicator: "#FFCB2B",
      sidebarHover:           "rgba(255,203,43,0.08)",
      shadowSm: "0 1px 3px rgba(0,0,0,0.40)",
      shadowMd: "0 4px 8px rgba(0,0,0,0.45)",
      shadowLg: "0 10px 24px rgba(0,0,0,0.55)",
    },
  },
};

export const typographyTokens = {
  fontFamilyAr: '"Segoe UI", "Tahoma", "Arabic Typesetting", system-ui, sans-serif',
  fontFamilyEn: '"Inter", "Segoe UI", system-ui, -apple-system, sans-serif',
  fontWeightRegular: 400,
  fontWeightMedium: 500,
  fontWeightSemibold: 600,
  fontWeightBold: 700,
  size: {
    xs: "0.6875rem",
    sm: "0.75rem",
    base: "0.875rem",
    md: "1rem",
    lg: "1.125rem",
    xl: "1.25rem",
    "2xl": "1.5rem",
    "3xl": "1.875rem",
  },
  lineHeight: { tight: 1.25, normal: 1.5, relaxed: 1.75 },
  letterSpacing: { tight: "-0.01em", normal: "0", wide: "0.04em" },
} as const;

export const radiusTokens = {
  none: 0, sm: 4, md: 6, lg: 8, xl: 12, "2xl": 16, full: 9999,
} as const;

export const zIndexTokens = {
  dropdown: 1000, sticky: 1020, overlay: 1040, modal: 1060, toast: 1100,
} as const;
