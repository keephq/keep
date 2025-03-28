// Menu.tsx
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
    "menu-minimized",
    false
  );

  useHotkeys(
    "[",
    () => {
      const newState = !isMenuMinimized;
      console.log(newState ? "Closing menu ([)" : "Opening menu ([)");
      setIsMenuMinimized(newState);
    },
    [isMenuMinimized]
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
            className={`relative bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-white col-span-1 border-r border-gray-300 dark:border-gray-700 h-full hidden lg:block ${
              isMenuMinimized ? "w-16" : "w-56"
            } transition-all duration-200 ease-in-out`}
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
