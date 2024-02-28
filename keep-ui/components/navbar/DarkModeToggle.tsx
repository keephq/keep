import { Icon, Switch } from "@tremor/react";
import { MdDarkMode } from "react-icons/md";
import { useTheme } from "next-themes";

export default function DarkModeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <div
      className="flex items-center justify-between space-x-3 w-full text-sm p-1 text-gray-700 hover:bg-gray-200 font-medium rounded-lg hover:text-orange-500 focus:ring focus:ring-orange-300 cursor-pointer"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      role="button"
    >
      <span className="flex items-center justify-between">
        <Icon className="text-gray-700" icon={MdDarkMode} color="orange" />
        <span>Dark Mode</span>
      </span>
      <Switch color="orange" checked={theme === "dark"} />
    </div>
  );
}
