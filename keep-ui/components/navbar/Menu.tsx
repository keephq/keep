"use client";

import { Fragment, ReactNode, useEffect } from "react";
import { Popover } from "@headlessui/react";
import { Icon } from "@tremor/react";
import { AiOutlineMenu, AiOutlineClose } from "react-icons/ai";
import { usePathname } from "next/navigation";

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
};

export const Menu = ({ children }: MenuButtonProps) => {
  return (
    <Popover as={Fragment}>
      {({ close: closeMenu }) => (
        <>
          <div className="p-4 w-full block lg:hidden">
            <Popover.Button>
              <Icon icon={AiOutlineMenu} color="orange" />
            </Popover.Button>
          </div>

          <aside className="bg-gray-50 col-span-1 border-r border-gray-300 h-full hidden lg:block">
            <nav className="flex flex-col h-full">{children}</nav>
          </aside>

          <CloseMenuOnRouteChange closeMenu={closeMenu} />
          <Popover.Panel
            className="bg-gray-50 col-span-1 border-r border-gray-300 z-50 h-screen fixed inset-0"
            as="nav"
          >
            <Popover.Button className="fixed top-0 right-0 p-4">
              <Icon icon={AiOutlineClose} color="orange" />
            </Popover.Button>
            {children}
          </Popover.Panel>
        </>
      )}
    </Popover>
  );
};
