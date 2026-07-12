import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";
import en from "./locales/en/common.json";
import ar from "./locales/ar/common.json";

export const RTL_LANGUAGES = ["ar"];
export type Direction = "ltr" | "rtl";

export function directionForLanguage(language: string): Direction {
  return RTL_LANGUAGES.includes(language) ? "rtl" : "ltr";
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { common: en },
      ar: { common: ar },
    },
    ns: ["common"],
    defaultNS: "common",
    fallbackLng: "ar",
    interpolation: { escapeValue: false },
  });

export default i18n;
