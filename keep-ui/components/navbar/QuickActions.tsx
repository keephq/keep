// QuickActions.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { Icon } from "@tremor/react";
import { FiSearch } from "react-icons/fi";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { RiCommandLine } from "react-icons/ri";
import { useSession } from "next-auth/react";
import { Popover, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { VscDebugDisconnect } from "react-icons/vsc";
import { AiOutlineAlert, AiOutlineGroup } from "react-icons/ai";
import { MdOutlineEngineering } from "react-icons/md";
import { LuWorkflow } from "react-icons/lu";
import {
  UserGroupIcon,
  GlobeAltIcon,
  EnvelopeIcon,
  KeyIcon,
} from "@heroicons/react/24/outline";
import {
  FileTextIcon,
  GitHubLogoIcon,
  TwitterLogoIcon,
} from "@radix-ui/react-icons";
import { useRouter } from "next/navigation";

export const QuickActions = () => {
  const [isMenuMinimized] = useLocalStorage<boolean>("menu-minimized", false);
  const router = useRouter();
  const [isMac, setIsMac] = useState(false);
  const { data: session } = useSession();
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setIsMac(navigator.platform.toLowerCase().includes("mac"));
  }, []);

  // Navigation options based on your original Search component
  const NAVIGATION_OPTIONS = [
    {
      icon: VscDebugDisconnect,
      label: "Go to the providers page",
      navigate: "/providers",
    },
    {
      icon: AiOutlineAlert,
      label: "Go to alert console",
      navigate: "/alerts/feed",
    },
    {
      icon: AiOutlineGroup,
      label: "Go to alert quality",
      navigate: "/alerts/quality",
    },
    {
      icon: MdOutlineEngineering,
      label: "Go to alert groups",
      navigate: "/rules",
    },
    {
      icon: LuWorkflow,
      label: "Go to the workflows page",
      navigate: "/workflows",
    },
    {
      icon: UserGroupIcon,
      label: "Go to users management",
      navigate: "/settings?selectedTab=users",
    },
    {
      icon: GlobeAltIcon,
      label: "Go to generic webhook",
      navigate: "/settings?selectedTab=webhook",
    },
    {
      icon: EnvelopeIcon,
      label: "Go to SMTP settings",
      navigate: "/settings?selectedTab=smtp",
    },
    {
      icon: KeyIcon,
      label: "Go to API key",
      navigate: "/settings?selectedTab=users&userSubTab=api-keys",
    },
  ];

  const EXTERNAL_OPTIONS = [
    {
      icon: FileTextIcon,
      label: "Keep Docs",
      navigate: "https://docs.keephq.dev",
    },
    {
      icon: GitHubLogoIcon,
      label: "Keep Source code",
      navigate: "https://github.com/keephq/keep",
    },
    {
      icon: TwitterLogoIcon,
      label: "Keep Twitter",
      navigate: "https://twitter.com/keepalerting",
    },
  ];

  const navigateTo = (path: string) => {
    // Close the popover
    if (buttonRef.current) {
      buttonRef.current.click();
    }

    // Check if it's an external link
    if (path.startsWith("http")) {
      window.open(path, "_blank");
    } else {
      router.push(path);
    }
  };

  // Listen for Cmd+K or Ctrl+K to open the menu
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        buttonRef.current?.click();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <Popover className="relative w-full">
      {({ open }) => (
        <>
          <Popover.Button
            ref={buttonRef}
            className={`text-left w-full rounded-md flex items-center px-3 py-2 text-gray-600 dark:text-gray-300 bg-gray-200 dark:bg-gray-800 hover:bg-gray-300 dark:hover:bg-gray-700 transition-colors ${
              isMenuMinimized ? "justify-center" : "justify-between"
            }`}
          >
            <div className="flex items-center">
              <Icon icon={FiSearch} className={isMenuMinimized ? "" : "mr-2"} />
              {!isMenuMinimized && <span>Go to...</span>}
            </div>
            {!isMenuMinimized && (
              <div className="flex items-center text-xs bg-gray-300 dark:bg-gray-700 px-1.5 py-0.5 rounded">
                {isMac ? (
                  <>
                    <Icon icon={RiCommandLine} size="xs" className="mr-0.5" />
                    <span>K</span>
                  </>
                ) : (
                  <>
                    <span>Ctrl+K</span>
                  </>
                )}
              </div>
            )}
          </Popover.Button>

          <Transition
            as={Fragment}
            enter="transition ease-out duration-200"
            enterFrom="opacity-0 translate-y-1"
            enterTo="opacity-100 translate-y-0"
            leave="transition ease-in duration-150"
            leaveFrom="opacity-100 translate-y-0"
            leaveTo="opacity-0 translate-y-1"
          >
            <Popover.Panel className="absolute z-10 mt-1 w-64 sm:w-96 max-h-96 overflow-y-auto rounded-md bg-white dark:bg-gray-800 shadow-lg">
              <div className="p-1">
                <div className="py-2 px-3">
                  <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">
                    Navigate
                  </h3>
                </div>
                {NAVIGATION_OPTIONS.map((option) => (
                  <button
                    key={option.label}
                    className="flex items-center w-full px-3 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
                    onClick={() => navigateTo(option.navigate)}
                  >
                    <Icon
                      icon={option.icon}
                      className="mr-2 text-gray-500 dark:text-gray-400"
                    />
                    <span>{option.label}</span>
                  </button>
                ))}

                <div className="py-2 px-3 mt-2 border-t border-gray-200 dark:border-gray-700">
                  <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">
                    External Sources
                  </h3>
                </div>
                {EXTERNAL_OPTIONS.map((option) => (
                  <button
                    key={option.label}
                    className="flex items-center w-full px-3 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
                    onClick={() => navigateTo(option.navigate)}
                  >
                    <Icon
                      icon={option.icon}
                      className="mr-2 text-gray-500 dark:text-gray-400"
                    />
                    <span>{option.label}</span>
                  </button>
                ))}
              </div>
            </Popover.Panel>
          </Transition>
        </>
      )}
    </Popover>
  );
};
