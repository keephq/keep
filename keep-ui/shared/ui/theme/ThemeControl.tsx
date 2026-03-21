import { LOCALSTORAGE_THEME_KEY } from "@/shared/constants";
import {
  ComputerDesktopIcon,
  MoonIcon,
  SunIcon,
} from "@heroicons/react/20/solid";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { DropdownMenu } from "@/shared/ui";
import clsx from "clsx";
import { useI18n } from "@/i18n/hooks/useI18n";

const THEMES = {
  light: { id: "light", icon: SunIcon, titleKey: "common.theme.light" },
  dark: { id: "dark", icon: MoonIcon, titleKey: "common.theme.dark" },
  system: {
    id: "system",
    icon: ComputerDesktopIcon,
    titleKey: "common.theme.system",
  },
};

export function ThemeControl({ className }: { className?: string }) {
  const { t } = useI18n();
  const [theme, setTheme] = useLocalStorage<string | null>(
    LOCALSTORAGE_THEME_KEY,
    null
  );

  const updateTheme = (theme: string) => {
    setTheme(theme === "system" ? null : theme);
    if (theme !== "system") {
      document.documentElement.classList[theme === "dark" ? "add" : "remove"](
        "workaround-dark"
      );
      // If system theme is selected, <WatchUpdateTheme /> will handle the rest
    }
  };

  const value = theme === null ? "system" : theme;

  return (
    <DropdownMenu.Menu
      icon={() => (
        <>
          <span className="workaround-dark-hidden">
            <SunIcon className="w-4 h-4" />
          </span>
          <span className="hidden workaround-dark-visible">
            <MoonIcon className="w-4 h-4" />
          </span>
        </>
      )}
      label=""
      className={clsx(value !== "system" && "text-tremor-brand", className)}
    >
      {Object.values(THEMES).map(({ id, icon: Icon, titleKey }) => (
        <DropdownMenu.Item
          key={id}
          icon={Icon}
          label={t(titleKey)}
          onClick={() => updateTheme(id)}
          className={clsx(id === value && "text-tremor-brand")}
        />
      ))}
    </DropdownMenu.Menu>
  );
}
