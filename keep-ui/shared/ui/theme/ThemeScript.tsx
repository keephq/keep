"use client";

import { LOCALSTORAGE_THEME_KEY } from "../../constants";

export const ThemeScript = () => {
  return (
    <script
      dangerouslySetInnerHTML={{
        __html: `
          (function() {
            try {
              // First, remove any existing theme class to ensure a clean state
              // This ensures we start from a consistent state on both server and client
              document.documentElement.classList.remove("workaround-dark");

              // Only apply theme after hydration is complete
              // This ensures the server and client render the same initial HTML
              if (typeof window !== 'undefined') {
                // Use requestAnimationFrame to ensure we run after React hydration
                window.requestAnimationFrame(() => {
                  let theme = localStorage.getItem('keephq-${LOCALSTORAGE_THEME_KEY}');
                  if (theme) {
                    try {
                      theme = JSON.parse(theme);
                    } catch (e) {
                      theme = null;
                    }
                  }

                  if (!theme) {
                    theme = window.matchMedia('(prefers-color-scheme: dark)').matches
                      ? 'dark'
                      : 'light'
                  }

                  // Apply the theme class after hydration is complete
                  if (theme === 'dark') {
                    document.documentElement.classList.add("workaround-dark");
                  }
                });
              }
            } catch (e) {
              console.error('Error in ThemeScript:', e);
            }
          })();
        `,
      }}
    />
  );
};
