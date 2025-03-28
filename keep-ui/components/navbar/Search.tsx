"use client";

import { ElementRef, Fragment, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon, List, ListItem, Subtitle } from "@tremor/react";
import {
  Combobox,
  ComboboxInput,
  ComboboxOption,
  ComboboxOptions,
  Transition,
} from "@headlessui/react";
import {
  GitHubLogoIcon,
  FileTextIcon,
  TwitterLogoIcon,
} from "@radix-ui/react-icons";
import {
  GlobeAltIcon,
  UserGroupIcon,
  EnvelopeIcon,
  KeyIcon,
  MagnifyingGlassIcon,
} from "@heroicons/react/24/outline";
import { VscDebugDisconnect } from "react-icons/vsc";
import { LuWorkflow } from "react-icons/lu";
import { AiOutlineAlert, AiOutlineGroup } from "react-icons/ai";
import { MdOutlineEngineering, MdOutlineSearchOff } from "react-icons/md";
import { useConfig } from "utils/hooks/useConfig";
import { Session } from "next-auth";

const NAVIGATION_OPTIONS = [
  {
    icon: VscDebugDisconnect,
    label: "Go to the providers page",
    shortcut: ["p"],
    navigate: "/providers",
  },
  {
    icon: AiOutlineAlert,
    label: "Go to alert console",
    shortcut: ["g"],
    navigate: "/alerts/feed",
  },
  {
    icon: AiOutlineGroup,
    label: "Go to alert quality",
    shortcut: ["q"],
    navigate: "/alerts/quality",
  },
  {
    icon: MdOutlineEngineering,
    label: "Go to alert groups",
    shortcut: ["g"],
    navigate: "/rules",
  },
  {
    icon: LuWorkflow,
    label: "Go to the workflows page",
    shortcut: ["wf"],
    navigate: "/workflows",
  },
  {
    icon: UserGroupIcon,
    label: "Go to users management",
    shortcut: ["u"],
    navigate: "/settings?selectedTab=users",
  },
  {
    icon: GlobeAltIcon,
    label: "Go to generic webhook",
    shortcut: ["w"],
    navigate: "/settings?selectedTab=webhook",
  },
  {
    icon: EnvelopeIcon,
    label: "Go to SMTP settings",
    shortcut: ["s"],
    navigate: "/settings?selectedTab=smtp",
  },
  {
    icon: KeyIcon,
    label: "Go to API key",
    shortcut: ["a"],
    navigate: "/settings?selectedTab=users&userSubTab=api-keys",
  },
];

interface SearchProps {
  session: Session | null;
}

export const Search = ({ session }: SearchProps) => {
  const [query, setQuery] = useState<string>("");
  const [, setSelectedOption] = useState<string | null>(null);
  const router = useRouter();
  const comboboxInputRef = useRef<ElementRef<"input">>(null);
  const { data: configData } = useConfig();
  const docsUrl = configData?.KEEP_DOCS_URL || "https://docs.keephq.dev";

  const EXTERNAL_OPTIONS = [
    {
      icon: FileTextIcon,
      label: "Keep Docs",
      shortcut: ["⇧", "D"],
      navigate: docsUrl,
    },
    {
      icon: GitHubLogoIcon,
      label: "Keep Source code",
      shortcut: ["⇧", "C"],
      navigate: "https://github.com/keephq/keep",
    },
    {
      icon: TwitterLogoIcon,
      label: "Keep Twitter",
      shortcut: ["⇧", "T"],
      navigate: "https://twitter.com/keepalerting",
    },
  ];

  const OPTIONS = [...NAVIGATION_OPTIONS, ...EXTERNAL_OPTIONS];

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        if (comboboxInputRef.current) {
          comboboxInputRef.current.focus();
        }
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const onOptionSelection = (value: string | null) => {
    setSelectedOption(value);
    if (value && comboboxInputRef.current) {
      comboboxInputRef.current.blur();
      router.push(value);
    }
  };

  const onLeave = () => {
    setQuery("");

    if (comboboxInputRef.current) {
      comboboxInputRef.current.blur();
    }
  };

  const queriedOptions = query.length
    ? OPTIONS.filter((option) =>
        option.label
          .toLowerCase()
          .replace(/\s+/g, "")
          .includes(query.toLowerCase().replace(/\s+/g, ""))
      )
    : OPTIONS;

  const NoQueriesFoundResult = () => {
    if (query.length && queriedOptions.length === 0) {
      return (
        <ListItem className="flex flex-col items-center justify-center cursor-default select-none px-4 py-2 text-gray-700 h-72">
          <Icon color="orange" size="xl" icon={MdOutlineSearchOff} />
          Nothing found.
        </ListItem>
      );
    }

    return null;
  };

  const FilteredResults = () => {
    if (query.length && queriedOptions.length) {
      return (
        <>
          {queriedOptions.map((option) => (
            <ComboboxOption
              key={option.label}
              as={Fragment}
              value={option.navigate}
            >
              {({ active }) => (
                <ListItem className="flex items-center justify-start space-x-3 cursor-default select-none p-2 ui-active:bg-orange-400 ui-active:text-white ui-not-active:text-gray-900">
                  <Icon
                    className={`py-2 px-0 ${
                      active ? "bg-orange-400 text-white" : "text-gray-900"
                    }`}
                    icon={option.icon}
                    color="orange"
                  />
                  <span className="text-left">{option.label}</span>
                </ListItem>
              )}
            </ComboboxOption>
          ))}
        </>
      );
    }

    return null;
  };

  const DefaultResults = () => {
    if (query.length) {
      return null;
    }

    return (
      <ListItem className="flex flex-col">
        <List>
          <ListItem className="pl-2">
            <Subtitle>Navigate</Subtitle>
          </ListItem>
          {NAVIGATION_OPTIONS.map((option) => (
            <ComboboxOption
              key={option.label}
              as={Fragment}
              value={option.navigate}
            >
              {({ active }) => (
                <ListItem className="flex items-center justify-start space-x-3 cursor-default select-none p-2 ui-active:bg-orange-400 ui-active:text-white ui-not-active:text-gray-900">
                  <Icon
                    className={`py-2 px-0 ${
                      active ? "bg-orange-400 text-white" : "text-gray-900"
                    }`}
                    icon={option.icon}
                    color="orange"
                  />
                  <span className="text-left">{option.label}</span>
                </ListItem>
              )}
            </ComboboxOption>
          ))}
        </List>
        <List>
          <ListItem className="pl-2">
            <Subtitle>External Sources</Subtitle>
          </ListItem>
          {EXTERNAL_OPTIONS.map((option) => (
            <ComboboxOption
              key={option.label}
              as={Fragment}
              value={option.navigate}
            >
              {({ active }) => (
                <ListItem className="flex items-center justify-start space-x-3 cursor-default select-none p-2 ui-active:bg-orange-400 ui-active:text-white ui-not-active:text-gray-900">
                  <Icon
                    className={`py-2 px-0 ${
                      active ? "bg-orange-400 text-white" : "text-gray-900"
                    }`}
                    icon={option.icon}
                    color="orange"
                  />
                  <span className="text-left">{option.label}</span>
                </ListItem>
              )}
            </ComboboxOption>
          ))}
        </List>
      </ListItem>
    );
  };

  const isMac = () => {
    const platform = navigator.platform.toLowerCase();
    const userAgent = navigator.userAgent.toLowerCase();
    return (
      platform.includes("mac") ||
      (platform.includes("iphone") && !userAgent.includes("windows"))
    );
  };

  const [placeholderText, setPlaceholderText] = useState("Search");

  // Using effect to avoid mismatch on hydration. TODO: context provider for user agent
  useEffect(function updatePlaceholderText() {
    if (!isMac()) {
      return;
    }
    setPlaceholderText("Search (or ⌘K)");
  }, []);

  return (
    <div className="flex items-center w-full">
      <Combobox
        value={query}
        onChange={onOptionSelection}
        as="div"
        className="relative w-full"
        immediate
      >
        {({ open }) => (
          <>
            {open && (
              <div
                className="fixed inset-0 bg-black/40 z-10"
                aria-hidden="true"
              />
            )}

            <div className="flex bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-md items-center transition-all duration-200">
              <MagnifyingGlassIcon className="h-4 w-4 ml-2 text-gray-500 dark:text-gray-400" />
              <ComboboxInput
                className="z-20 bg-transparent border-none w-full px-2 py-1.5 text-sm focus:outline-none focus:ring-0 dark:text-gray-300 placeholder:text-gray-500 dark:placeholder:text-gray-400"
                placeholder={placeholderText}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                ref={comboboxInputRef}
              />
              <div className="flex items-center bg-gray-200 dark:bg-gray-700 rounded px-1.5 mr-2 text-xs text-gray-600 dark:text-gray-400">
                <span>⌘</span>
                <span className="mx-0.5">+</span>
                <span>K</span>
              </div>
            </div>

            <Transition
              as={Fragment}
              beforeLeave={onLeave}
              leave="transition ease-in duration-100"
              leaveFrom="opacity-100"
              leaveTo="opacity-0"
            >
              <ComboboxOptions
                className="absolute mt-1 max-h-screen overflow-auto rounded-md bg-white shadow-lg ring-1 ring-black/5 focus:outline-none z-20 w-96"
                as={List}
              >
                <NoQueriesFoundResult />
                <FilteredResults />
                <DefaultResults />
              </ComboboxOptions>
            </Transition>
          </>
        )}
      </Combobox>
    </div>
  );
};
