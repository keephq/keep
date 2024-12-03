"use client";

import { useCallback } from "react";
import { useEffect } from "react";
import { LOCALSTORAGE_THEME_KEY } from "../../constants";
import { useLocalStorage } from "utils/hooks/useLocalStorage";

export const ThemeScript = () => {
  const [theme] = useLocalStorage(LOCALSTORAGE_THEME_KEY, null);

  const updateThemeFromMediaPreference = useCallback(() => {
    if (theme !== null) {
      return;
    }
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.classList[isDark ? "add" : "remove"](
      "workaround-dark"
    );
  }, [theme]);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = (e: MediaQueryListEvent) => {
      updateThemeFromMediaPreference();
    };
    mediaQuery.addEventListener("change", listener);
    return () => {
      mediaQuery.removeEventListener("change", listener);
    };
  }, [updateThemeFromMediaPreference]);

  return (
    <script
      dangerouslySetInnerHTML={{
        __html: `
          try {
            let theme = localStorage.getItem('keephq-${LOCALSTORAGE_THEME_KEY}');
            if (theme) {
                theme = JSON.parse(theme);
            }

            if (!theme) {
              theme = window.matchMedia('(prefers-color-scheme: dark)').matches
                ? 'dark'
                : 'light'
            }

            document.documentElement.classList[theme === "dark" ? "add" : "remove"](
              "workaround-dark"
            );
          } catch (e) {}
        `,
      }}
    />
  );
};
