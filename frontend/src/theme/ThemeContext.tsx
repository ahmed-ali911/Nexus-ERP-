import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { CacheProvider } from "@emotion/react";
import { ThemeProvider as MuiThemeProvider, CssBaseline } from "@mui/material";
import { useTranslation } from "react-i18next";
import { buildEmotionCache, buildMuiTheme } from "./createAppTheme";
import { type ColorMode, type PaletteId } from "./tokens";
import { directionForLanguage, type Direction } from "@/i18n";

interface AppThemeContextValue {
  mode: ColorMode;
  palette: PaletteId;
  direction: Direction;
  setMode: (mode: ColorMode) => void;
  toggleMode: () => void;
  setPalette: (palette: PaletteId) => void;
}

const AppThemeContext = createContext<AppThemeContextValue | null>(null);

export function AppThemeProvider({ children }: { children: React.ReactNode }) {
  const { i18n } = useTranslation();
  const [mode, setMode] = useState<ColorMode>("light");
  const [palette, setPalette] = useState<PaletteId>("ocean");

  const direction = directionForLanguage(i18n.language);

  useEffect(() => {
    document.documentElement.dir = direction;
    document.documentElement.lang = i18n.language;
  }, [direction, i18n.language]);

  const cache = useMemo(() => buildEmotionCache(direction), [direction]);
  const theme = useMemo(() => buildMuiTheme(palette, mode, direction), [palette, mode, direction]);

  const toggleMode = () => setMode((m) => (m === "light" ? "dark" : "light"));

  return (
    <AppThemeContext.Provider value={{ mode, palette, direction, setMode, toggleMode, setPalette }}>
      <CacheProvider value={cache}>
        <MuiThemeProvider theme={theme}>
          <CssBaseline />
          {children}
        </MuiThemeProvider>
      </CacheProvider>
    </AppThemeContext.Provider>
  );
}

export function useAppTheme(): AppThemeContextValue {
  const ctx = useContext(AppThemeContext);
  if (!ctx) throw new Error("useAppTheme must be used inside AppThemeProvider");
  return ctx;
}
