"use client";

import { LOCALSTORAGE_THEME_KEY } from "@/shared/constants";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { useCallback, useEffect } from "react";

export function WatchUpdateTheme() {
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
  return null;
}
