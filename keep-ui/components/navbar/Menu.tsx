"use client";

import { ReactNode, useEffect } from "react";
import { Popover } from "@headlessui/react";
import { Icon } from "@tremor/react";
import { AiOutlineMenu, AiOutlineClose } from "react-icons/ai";
import { usePathname } from "next/navigation";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { useHotkeys } from "react-hotkeys-hook";
import { Session } from "next-auth";

type CloseMenuOnRouteChangeProps = {
  closeMenu: () => void;
};

const CloseMenuOnRouteChange = ({ closeMenu }: CloseMenuOnRouteChangeProps) => {
  const pathname = usePathname();

  useEffect(() => {
    closeMenu();
  }, [pathname, closeMenu]);

  return null;
};

type MenuButtonProps = {
  children: ReactNode;
  session: Session | null;
};

export const Menu = ({ children, session }: MenuButtonProps) => {
  const [isMenuMinimized, setIsMenuMinimized] = useLocalStorage<boolean>(
    "sidebar-minimized", // Changed from "menu-minimized" to match MinimizeMenuButton
    false
  );

  // Listen for events from MinimizeMenuButton
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === "sidebar-minimized") {
        setIsMenuMinimized(e.newValue === "true");
      }
    };

    // Custom event for same-tab communication
    const handleCustomEvent = (e) => {
      if (e.detail && e.detail.key === "sidebar-minimized") {
        setIsMenuMinimized(e.detail.value === "true");
      }
    };

    window.addEventListener("storage", handleStorageChange);
    window.addEventListener("sidebarStateChange", handleCustomEvent);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("sidebarStateChange", handleCustomEvent);
    };
  }, [setIsMenuMinimized]);

  useHotkeys(
    "[",
    () => {
      const newState = !isMenuMinimized;
      console.log(newState ? "Closing menu ([)" : "Opening menu ([)");
      setIsMenuMinimized(newState);

      // Notify MinimizeMenuButton of the change
      localStorage.setItem("sidebar-minimized", String(newState));
      window.dispatchEvent(
        new CustomEvent("sidebarStateChange", {
          detail: { key: "sidebar-minimized", value: String(newState) },
        })
      );
    },
    [isMenuMinimized, setIsMenuMinimized]
  );

  return (
    <Popover>
      {({ close: closeMenu }) => (
        <>
          <div className="p-3 w-full block lg:hidden">
            <Popover.Button className="p-1 hover:bg-stone-200/50 dark:hover:bg-gray-700 font-medium rounded-lg hover:text-orange-400 dark:hover:text-orange-400 focus:ring focus:ring-orange-300">
              <Icon icon={AiOutlineMenu} color="orange" />
            </Popover.Button>
          </div>

          <aside
            className={`relative bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-white col-span-1 border-r border-gray-300 dark:border-gray-700 h-full hidden lg:block transition-all duration-200 ease-in-out overflow-hidden ${
              isMenuMinimized ? "w-16" : "w-52"
            }`}
            data-minimized={isMenuMinimized}
          >
            {children}
          </aside>

          <CloseMenuOnRouteChange closeMenu={closeMenu} />
          <Popover.Panel
            className="bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-white col-span-1 border-r border-gray-300 dark:border-gray-700 z-50 h-screen fixed inset-0 w-64"
            as="nav"
          >
            <div className="p-3 fixed top-0 right-0">
              <Popover.Button className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 font-medium rounded-lg text-gray-800 dark:text-white focus:ring focus:ring-gray-300 dark:focus:ring-gray-600">
                <Icon icon={AiOutlineClose} color="gray" />
              </Popover.Button>
            </div>

            <div className="mt-12">{children}</div>
          </Popover.Panel>
        </>
      )}
    </Popover>
  );
};
