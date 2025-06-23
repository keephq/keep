"use client";

import { LOCALSTORAGE_THEME_KEY } from "../../constants";

export const ThemeScript = () => {
  return (
    <script
      // eslint-disable-next-line react/no-danger -- the script is trusted and LOCALSTORAGE_THEME_KEY is constant and not user-controlled
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
