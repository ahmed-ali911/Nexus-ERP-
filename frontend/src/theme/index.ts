import createCache from "@emotion/cache";
import { createTheme } from "@mui/material/styles";
import { prefixer } from "stylis";
import rtlPlugin from "stylis-plugin-rtl";

import { RTL_LANGUAGES } from "../i18n";

export type Direction = "ltr" | "rtl";

export function directionForLanguage(language: string): Direction {
  return RTL_LANGUAGES.includes(language) ? "rtl" : "ltr";
}

export function createEmotionCache(direction: Direction) {
  return direction === "rtl"
    ? createCache({ key: "mui-rtl", stylisPlugins: [prefixer, rtlPlugin] })
    : createCache({ key: "mui-ltr" });
}

export function createAppTheme(direction: Direction) {
  return createTheme({
    direction,
    palette: { mode: "light" },
  });
}
