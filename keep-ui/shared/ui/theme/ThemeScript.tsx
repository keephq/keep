"use client";

import { LOCALSTORAGE_THEME_KEY } from "../../constants";

export const ThemeScript = () => {
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
