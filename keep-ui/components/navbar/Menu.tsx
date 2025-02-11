"use client";

import { Fragment, ReactNode, useEffect } from "react";
import { Popover } from "@headlessui/react";
import { Icon } from "@tremor/react";
import { AiOutlineMenu, AiOutlineClose } from "react-icons/ai";
import { usePathname } from "next/navigation";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { useHotkeys } from 'react-hotkeys-hook';

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
  const [isMenuMinimized, setisMenuMinimized] = useLocalStorage<boolean>("menu-minimized", false);

  useHotkeys('[', () => {
    // Toggle the state based on its current value
    const newState = !isMenuMinimized;
    console.log(newState ? 'Closing menu ([)' : 'Opening menu ([)');
    setisMenuMinimized(newState);
  }, [isMenuMinimized]);


  return (
    <Popover as={Fragment}>
      {({ close: closeMenu }) => (
        <>
          <div className="p-3 w-full block lg:hidden">
            <Popover.Button className="p-1 hover:bg-stone-200/50 font-medium rounded-lg hover:text-orange-400 focus:ring focus:ring-orange-300">
              <Icon icon={AiOutlineMenu} color="orange" />
            </Popover.Button>
          </div>

          <aside
            className='relative pb-12 bg-gray-50 col-span-1 border-r border-gray-300 h-full hidden lg:block [&[data-minimized="true"]>nav]:invisible'
            data-minimized={isMenuMinimized}
          >
            <nav className="flex flex-col h-full">{children}</nav>
          </aside>

          <CloseMenuOnRouteChange closeMenu={closeMenu} />
          <Popover.Panel
            className="bg-gray-50 col-span-1 border-r border-gray-300 z-50 h-screen fixed inset-0"
            as="nav"
          >
            <div className="p-3 fixed top-0 right-0 ">
              <Popover.Button className="p-1 hover:bg-stone-200/50 font-medium rounded-lg hover:text-orange-400 focus:ring focus:ring-orange-300">
                <Icon icon={AiOutlineClose} color="orange" />
              </Popover.Button>
            </div>

            {children}
          </Popover.Panel>
        </>
      )}
    </Popover>
  );
};
