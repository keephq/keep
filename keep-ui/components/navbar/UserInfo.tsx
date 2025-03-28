// UserInfo.tsx
"use client";

import { Session } from "next-auth";
import Image from "next/image";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import Link from "next/link";
import { FiMessageSquare } from "react-icons/fi";
import { Icon } from "@tremor/react";
import { Menu, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { ThemeControl } from "@/shared/ui";
import { VscDebugDisconnect } from "react-icons/vsc";
import { FaSlack } from "react-icons/fa";
import { HiOutlineDocumentText } from "react-icons/hi2";
import { useConfig } from "utils/hooks/useConfig";
import { Tooltip } from "@/shared/ui";

type UserInfoProps = {
  session: Session | null;
};

export const UserInfo = ({ session }: UserInfoProps) => {
  const [isMenuMinimized] = useLocalStorage<boolean>("menu-minimized", false);
  const { data: config } = useConfig();
  const docsUrl = config?.KEEP_DOCS_URL || "https://docs.keephq.dev";

  if (!session) return null;

  const userInitials = session.user?.name
    ? session.user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
    : session.user?.email?.slice(0, 2) || "U";

  return (
    <div className={`px-2 py-2 ${isMenuMinimized ? "text-center" : ""}`}>
      {/* First row: Providers link */}
      <Link
        href="/providers"
        className="flex items-center text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-800 rounded-md px-2 py-1.5 mb-2"
      >
        <Icon
          icon={VscDebugDisconnect}
          className={isMenuMinimized ? "" : "mr-2"}
        />
        {!isMenuMinimized && <span>Providers</span>}
      </Link>

      {/* Second row: User profile */}
      <Menu as="div" className="relative mb-2">
        <Menu.Button
          className={`flex ${
            isMenuMinimized ? "justify-center" : "items-center"
          } w-full cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-800 rounded-md py-1.5 px-2 transition-colors`}
        >
          <div className="flex-shrink-0">
            {session.user?.image ? (
              <Image
                src={session.user.image}
                alt="User"
                width={32}
                height={32}
                className="rounded-full"
              />
            ) : (
              <div className="h-8 w-8 rounded-full bg-orange-500 flex items-center justify-center text-white text-sm font-medium">
                {userInitials}
              </div>
            )}
          </div>

          {!isMenuMinimized && (
            <div className="ml-3 truncate">
              <div className="text-sm font-medium text-gray-700 dark:text-white truncate">
                {session.user?.name || session.user?.email || "User"}
              </div>
              {session.user?.tenantIds && session.user.tenantIds.length > 0 && (
                <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {session.user.tenantIds.find(
                    (t) => t.tenant_id === session.tenantId
                  )?.tenant_name || ""}
                </div>
              )}
            </div>
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
          <Menu.Items className="absolute right-0 bottom-full mb-1 w-48 origin-bottom-right rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black/5 dark:ring-white/5 focus:outline-none">
            <div className="py-1">
              <Menu.Item>
                {({ active }) => (
                  <Link
                    href="/settings"
                    className={`${
                      active ? "bg-gray-100 dark:bg-gray-700" : ""
                    } flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-200`}
                  >
                    Settings
                  </Link>
                )}
              </Menu.Item>
              <Menu.Item>
                {({ active }) => (
                  <Link
                    href="/api/auth/signout"
                    className={`${
                      active ? "bg-gray-100 dark:bg-gray-700" : ""
                    } flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-200`}
                  >
                    Sign out
                  </Link>
                )}
              </Menu.Item>
            </div>
          </Menu.Items>
        </Transition>
      </Menu>

      {/* Separator line */}
      <div className="border-t border-gray-200 dark:border-gray-700 mb-2"></div>

      {/* Bottom section with icons in DataDog style */}
      <div className="flex items-center justify-around space-x-2">
        <Tooltip content="Join our Slack community">
          <Link
            href="https://slack.keephq.dev/"
            target="_blank"
            className="flex flex-col items-center text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white transition-colors p-1"
            aria-label="Slack"
          >
            <Icon icon={FaSlack} className="w-6 h-6 mb-1" />
            <span className="text-xs">Slack</span>
          </Link>
        </Tooltip>

        <Tooltip content="Documentation">
          <Link
            href={docsUrl}
            target="_blank"
            className="flex flex-col items-center text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white transition-colors p-1"
            aria-label="Docs"
          >
            <Icon icon={HiOutlineDocumentText} className="w-6 h-6 mb-1" />
            <span className="text-xs">Docs</span>
          </Link>
        </Tooltip>

        <Tooltip content="Get support">
          <Link
            href="/support"
            className="flex flex-col items-center text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white transition-colors p-1"
            aria-label="Support"
          >
            <Icon icon={FiMessageSquare} className="w-6 h-6 mb-1" />
            <span className="text-xs">Support</span>
          </Link>
        </Tooltip>

        <Tooltip content="Toggle theme">
          <button className="flex flex-col items-center text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-white transition-colors p-1">
            <ThemeControl className="w-6 h-6 mb-1 flex items-center justify-center" />
            <span className="text-xs">Theme</span>
          </button>
        </Tooltip>
      </div>
    </div>
  );
};
