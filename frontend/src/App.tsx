import { useEffect, useMemo } from "react";
import { CacheProvider } from "@emotion/react";
import { Box, Button, CssBaseline, Stack, ThemeProvider, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";

import { createAppTheme, createEmotionCache, directionForLanguage } from "./theme";

function App() {
  const { t, i18n } = useTranslation();
  const direction = directionForLanguage(i18n.language);

  useEffect(() => {
    document.documentElement.dir = direction;
    document.documentElement.lang = i18n.language;
  }, [direction, i18n.language]);

  const cache = useMemo(() => createEmotionCache(direction), [direction]);
  const theme = useMemo(() => createAppTheme(direction), [direction]);

  return (
    <CacheProvider value={cache}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100vh",
            gap: 2,
          }}
        >
          <Typography variant="h3">{t("app.title")}</Typography>
          <Typography variant="body1" color="text.secondary">
            {t("app.tagline")}
          </Typography>
          <Stack direction="row" spacing={1}>
            <Button
              variant={i18n.language === "ar" ? "contained" : "outlined"}
              onClick={() => i18n.changeLanguage("ar")}
            >
              العربية
            </Button>
            <Button
              variant={i18n.language === "en" ? "contained" : "outlined"}
              onClick={() => i18n.changeLanguage("en")}
            >
              English
            </Button>
          </Stack>
        </Box>
      </ThemeProvider>
    </CacheProvider>
  );
}

export default App;
