import clsx from "clsx";

import { LOCALSTORAGE_THEME_KEY } from "@/shared/constants";
import { Cog6ToothIcon, MoonIcon, SunIcon } from "@heroicons/react/20/solid";
import { useLocalStorage } from "utils/hooks/useLocalStorage";

export function ThemeControl() {
  const [theme, setTheme] = useLocalStorage<string | null>(
    LOCALSTORAGE_THEME_KEY,
    null
  );

  const themes = [
    { id: "light", icon: SunIcon, title: "Light" },
    { id: "dark", icon: MoonIcon, title: "Dark" },
    { id: "system", icon: Cog6ToothIcon, title: "Based on your system" },
  ];

  const updateTheme = (theme: string) => {
    setTheme(theme === "system" ? null : theme);
    document.documentElement.classList[theme === "dark" ? "add" : "remove"](
      "workaround-dark"
    );
  };

  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-sm text-gray-500">Theme</span>

      <div className="rounded-lg flex gap-1">
        {themes.map(({ id, icon: Icon, title }) => {
          const value = theme === null ? "system" : theme;
          return (
            <button
              key={id}
              title={title}
              aria-label={title}
              onClick={() => updateTheme(id)}
              className={clsx(
                "p-2 rounded-md transition-all duration-200 relative",
                value === id
                  ? "bg-tremor-brand-muted text-tremor-brand"
                  : "text-gray-400 hover:text-tremor-brand hover:bg-gray-100"
              )}
            >
              <Icon className="w-4 h-4" />
            </button>
          );
        })}
      </div>
    </div>
  );
}
