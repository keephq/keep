"use client";

import { LOCALSTORAGE_THEME_KEY } from "@/shared/constants";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { useCallback, useEffect, useState } from "react";

export function WatchUpdateTheme() {
  const [theme] = useLocalStorage(LOCALSTORAGE_THEME_KEY, null);
  const [isLocalStorageReady, setIsLocalStorageReady] = useState(false);

  const setThemeClassName = (isDark: boolean) => {
    document.documentElement.classList[isDark ? "add" : "remove"](
      "workaround-dark"
    );
  };

  const updateThemeIfSystem = useCallback(
    (e: MediaQueryListEvent) => {
      if (theme !== null) {
        return;
      }
      setThemeClassName(e.matches);
    },
    [theme]
  );

  useEffect(() => {
    // Set up a listener for changes to the system theme
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    mediaQuery.addEventListener("change", updateThemeIfSystem);
    return () => {
      mediaQuery.removeEventListener("change", updateThemeIfSystem);
    };
  }, [updateThemeIfSystem]);

  useEffect(() => {
    // watch for theme preference changes and update if system selected and localstorage is ready
    setIsLocalStorageReady(true);
    if (theme !== null || !isLocalStorageReady) {
      return;
    }
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    setThemeClassName(mediaQuery.matches);
  }, [theme, isLocalStorageReady]);

  return null;
}
