// ProvidersLinks.tsx
"use client";

import { useState } from "react";
import { Session } from "next-auth";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@tremor/react";
import { FiLink, FiChevronDown, FiChevronRight } from "react-icons/fi";
import { useLocalStorage } from "utils/hooks/useLocalStorage";

type ProvidersLinksProps = {
  session: Session | null;
};

export const ProvidersLinks = ({ session }: ProvidersLinksProps) => {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(true);
  const [isMenuMinimized] = useLocalStorage<boolean>("menu-minimized", false);

  const isActive = (path: string) => pathname === path;

  return (
    <div className="mb-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center w-full text-left px-2 py-1.5 text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-white ${
          isMenuMinimized ? "justify-center" : "justify-between"
        }`}
      >
        {!isMenuMinimized && (
          <span className="text-xs font-semibold uppercase tracking-wider">
            PROVIDERS
          </span>
        )}
        {!isMenuMinimized && (
          <Icon
            icon={isOpen ? FiChevronDown : FiChevronRight}
            className="ml-2 opacity-70"
            size="sm"
          />
        )}
      </button>

      {(isOpen || isMenuMinimized) && (
        <div className="mt-1">
          <Link
            href="/providers"
            className={`flex items-center px-2 py-1.5 rounded-md ${
              isActive("/providers")
                ? "bg-blue-600 text-white"
                : "text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-800"
            } ${isMenuMinimized ? "justify-center" : ""}`}
          >
            <Icon icon={FiLink} className={isMenuMinimized ? "" : "mr-2"} />
            {!isMenuMinimized && <span>Providers</span>}
          </Link>

          <Link
            href="/slack"
            className={`flex items-center px-2 py-1.5 rounded-md ${
              isActive("/slack")
                ? "bg-blue-600 text-white"
                : "text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-800"
            } ${isMenuMinimized ? "justify-center" : ""}`}
          >
            <svg
              className={`w-5 h-5 ${isMenuMinimized ? "" : "mr-2"}`}
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" />
            </svg>
            {!isMenuMinimized && <span>Slack</span>}
          </Link>
        </div>
      )}
    </div>
  );
};
