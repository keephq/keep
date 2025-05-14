"use client";

import { LOCALSTORAGE_THEME_KEY } from "@/shared/constants";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { useCallback, useEffect, useState } from "react";

export function WatchUpdateTheme() {
  const [theme] = useLocalStorage(LOCALSTORAGE_THEME_KEY, null);
  const [isLocalStorageReady, setIsLocalStorageReady] = useState(false);

  const setThemeClassName = (isDark: boolean) => {
    // Use a more controlled approach to avoid hydration issues
    if (isDark) {
      document.documentElement.classList.add("workaround-dark");
    } else {
      document.documentElement.classList.remove("workaround-dark");
    }
  };

  const updateThemeIfSystem = useCallback(
    (e: MediaQueryListEvent) => {
      if (theme !== null) {
        return;
      }
      // Only update after initial render to avoid hydration issues
      requestAnimationFrame(() => {
        setThemeClassName(e.matches);
      });
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
    // Only run this effect on the client side after hydration
    if (typeof window === 'undefined') return;

    // watch for theme preference changes and update if system selected and localstorage is ready
    setIsLocalStorageReady(true);

    // Use requestAnimationFrame to ensure we run after React hydration
    requestAnimationFrame(() => {
      if (theme === 'dark') {
        setThemeClassName(true);
      } else if (theme === 'light') {
        setThemeClassName(false);
      } else if (isLocalStorageReady) {
        // If theme is null (system preference), check the system preference
        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        setThemeClassName(mediaQuery.matches);
      }
    });
  }, [theme, isLocalStorageReady]);

  return null;
}
