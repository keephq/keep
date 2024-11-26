import { Icon, Subtitle, Switch } from "@tremor/react";
import { useEffect, useState } from "react";
import { MdDarkMode } from "react-icons/md";

export default function DarkModeToggle() {
  const [darkMode, setDarkMode] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const localDarkMode = localStorage.getItem("keephq-darkMode");
      let initialDarkMode;

      if (localDarkMode !== null) {
        // Use the value from localStorage if it exists
        initialDarkMode = JSON.parse(localDarkMode);
      } else {
        // Otherwise, use the system preference
        initialDarkMode = window.matchMedia(
          "(prefers-color-scheme: dark)"
        ).matches;
      }

      setDarkMode(initialDarkMode);

      // Apply styles based on the initial dark mode setting
      if (initialDarkMode) {
        applyDarkModeStyles();
      }
    }
  }, []);

  useEffect(() => {
    if (darkMode !== null) {
      localStorage.setItem("keephq-darkMode", JSON.stringify(darkMode));

      if (darkMode) {
        applyDarkModeStyles();
      } else {
        removeDarkModeStyles();
      }
    }
  }, [darkMode]);

  const applyDarkModeStyles = () => {
    /**
     * Taken from https://dev.to/jochemstoel/re-add-dark-mode-to-any-website-with-just-a-few-lines-of-code-phl
     */
    const head = document.getElementsByTagName("head")[0];
    const styleElement = document.createElement("style");
    styleElement.setAttribute("type", "text/css");
    styleElement.setAttribute("id", "nightify");
    styleElement.appendChild(
      document.createTextNode(
        "html{-webkit-filter:invert(100%) hue-rotate(180deg) contrast(80%) !important; background: #fff;} .line-content {background-color: #fefefe;}"
      )
    );
    head.appendChild(styleElement);
  };

  const removeDarkModeStyles = () => {
    const existingStyles = document.querySelectorAll("#nightify");
    if (existingStyles.length) {
      existingStyles.forEach((style) => style.parentNode?.removeChild(style));
    }
  };

  const toggleDarkMode = () => {
    setDarkMode((prevMode) => !prevMode);
  };

  return (
    <label
      htmlFor="dark-mode"
      className="flex items-center justify-between space-x-3 w-full text-sm p-1 text-slate-400 hover:bg-stone-200/50 font-medium rounded-lg hover:text-orange-400 focus:ring focus:ring-orange-300 group"
    >
      <span className="flex items-center justify-between">
        <Icon
          className="text-black group-hover:text-orange-400"
          icon={MdDarkMode}
        />
        <Subtitle className="ml-2">Dark Mode</Subtitle>
      </span>
      <Switch
        id="dark-mode"
        name="dark-mode"
        color="orange"
        onChange={toggleDarkMode}
        checked={darkMode}
      />
    </label>
  );
}
