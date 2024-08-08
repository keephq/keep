"use client";

import { Icon } from "@tremor/react";
import { TbChevronCompactRight, TbChevronCompactLeft } from "react-icons/tb";
import { useLocalStorage } from "utils/hooks/useLocalStorage";

export const MinimizeMenuButton = () => {
  const [isMenuMinimized, setisMenuMinimized] = useLocalStorage<boolean>(
    "menu-minimized",
    false
  );

  return (
    <div className="hidden lg:flex items-center h-full jusity-center">
      <button
        className="flex items-center justify-center"
        onClick={() => setisMenuMinimized(!isMenuMinimized)}
      >
        <Icon
          className="text-slate-600 p-0 opacity-50 hover:opacity-100"
          icon={isMenuMinimized ? TbChevronCompactRight : TbChevronCompactLeft}
          size="lg"
        />
      </button>
    </div>
  );
};
