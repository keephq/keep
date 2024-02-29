import { useEffect, useState } from "react";
import { Icon, Subtitle, Switch } from "@tremor/react";
import { MdDarkMode } from "react-icons/md";
import { useTheme } from "next-themes";
import { CgSpinner } from "react-icons/cg";

export default function DarkModeToggle() {
  const [mounted, setMounted] = useState(false);
  const { theme, setTheme } = useTheme();

  // useEffect only runs on the client, so now we can safely show the UI
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="flex items-center justify-between space-x-3 w-full text-sm p-1 font-medium rounded-lg hover:text-orange-500 focus:ring focus:ring-orange-300 cursor-disabled">
        <span className="flex-1 flex items-center">
          <Icon
            className="text-gray-700 dark:text-gray-300"
            icon={MdDarkMode}
            color="orange"
          />
          <Subtitle>Dark Mode</Subtitle>
        </span>
        <Icon
          className="text-gray-700 dark:text-gray-300 animate-spin"
          icon={CgSpinner}
          color="orange"
        />
      </div>
    );
  }

  return (
    <div
      className="flex items-center justify-between space-x-3 w-full text-sm p-1 hover:bg-gray-200 dark:hover:bg-gray-700 font-medium rounded-lg hover:text-orange-500 focus:ring focus:ring-orange-300 cursor-pointer"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      role="button"
    >
      <span className="flex items-center justify-between">
        <Icon
          className="text-gray-700 dark:text-gray-300"
          icon={MdDarkMode}
          color="orange"
        />
        <Subtitle>Dark Mode</Subtitle>
      </span>
      <Switch color="orange" checked={theme === "dark"} />
    </div>
  );
}
