// ThemeToggle.tsx
"use client";

import { useState, useEffect } from "react";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { Menu, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { FiSun, FiMoon, FiMonitor } from "react-icons/fi";
import { Icon } from "@tremor/react";

type Theme = "light" | "dark" | "system";

export const ThemeToggle = () => {
  const [isMenuMinimized] = useLocalStorage<boolean>("menu-minimized", false);
  const [theme, setTheme] = useState<Theme>("system");

  useEffect(() => {
    // Get initial theme from localStorage or default to system
    const savedTheme = localStorage.getItem("theme") as Theme | null;
    if (savedTheme) {
      setTheme(savedTheme);
    }
  }, []);

  const applyTheme = (newTheme: Theme) => {
    setTheme(newTheme);
    localStorage.setItem("theme", newTheme);

    // Apply theme to HTML element
    const htmlElement = document.documentElement;

    if (
      newTheme === "dark" ||
      (newTheme === "system" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches)
    ) {
      htmlElement.classList.add("dark");
    } else {
      htmlElement.classList.remove("dark");
    }
  };

  useEffect(() => {
    // Apply theme on component mount and when theme changes
    applyTheme(theme);

    // Set up listener for system theme changes
    if (theme === "system") {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      const handleChange = () => {
        applyTheme("system");
      };

      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }
  }, [theme]);

  const getThemeIcon = () => {
    switch (theme) {
      case "light":
        return <Icon icon={FiSun} />;
      case "dark":
        return <Icon icon={FiMoon} />;
      case "system":
        return <Icon icon={FiMonitor} />;
    }
  };

  return (
    <Menu as="div" className="relative inline-block text-left w-full">
      {({ open }) => (
        <>
          <Menu.Button
            className={`flex items-center w-full px-2 py-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-800 ${
              isMenuMinimized ? "justify-center" : "justify-between"
            }`}
          >
            {isMenuMinimized ? (
              getThemeIcon()
            ) : (
              <>
                <div className="flex items-center">
                  {getThemeIcon()}
                  <span className="ml-2 capitalize">{theme}</span>
                </div>
                <span className="text-xs opacity-70">↓</span>
              </>
            )}
          </Menu.Button>

          <Transition
            as={Fragment}
            enter="transition ease-out duration-100"
            enterFrom="transform opacity-0 scale-95"
            enterTo="transform opacity-100 scale-100"
            leave="transition ease-in duration-75"
            leaveFrom="transform opacity-100 scale-100"
            leaveTo="transform opacity-0 scale-95"
          >
            <Menu.Items className="absolute right-0 bottom-full mb-1 z-10 w-40 origin-bottom-right bg-white dark:bg-gray-800 rounded-md shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
              <div className="py-1">
                <Menu.Item>
                  {({ active }) => (
                    <button
                      className={`${
                        active ? "bg-gray-100 dark:bg-gray-700" : ""
                      } ${
                        theme === "light" ? "bg-gray-200 dark:bg-gray-600" : ""
                      } flex items-center w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200`}
                      onClick={() => applyTheme("light")}
                    >
                      <Icon icon={FiSun} className="mr-2" />
                      Light
                    </button>
                  )}
                </Menu.Item>
                <Menu.Item>
                  {({ active }) => (
                    <button
                      className={`${
                        active ? "bg-gray-100 dark:bg-gray-700" : ""
                      } ${
                        theme === "dark" ? "bg-gray-200 dark:bg-gray-600" : ""
                      } flex items-center w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200`}
                      onClick={() => applyTheme("dark")}
                    >
                      <Icon icon={FiMoon} className="mr-2" />
                      Dark
                    </button>
                  )}
                </Menu.Item>
                <Menu.Item>
                  {({ active }) => (
                    <button
                      className={`${
                        active ? "bg-gray-100 dark:bg-gray-700" : ""
                      } ${
                        theme === "system" ? "bg-gray-200 dark:bg-gray-600" : ""
                      } flex items-center w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200`}
                      onClick={() => applyTheme("system")}
                    >
                      <Icon icon={FiMonitor} className="mr-2" />
                      System
                    </button>
                  )}
                </Menu.Item>
              </div>
            </Menu.Items>
          </Transition>
        </>
      )}
    </Menu>
  );
};
