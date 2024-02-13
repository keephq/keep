"use client";

import { ElementRef, Fragment, useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Icon, List, ListItem, TextInput, Subtitle } from "@tremor/react";
import { Combobox, Transition } from "@headlessui/react";
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
} from "@heroicons/react/24/outline";
import { VscDebugDisconnect } from "react-icons/vsc";
import { LuWorkflow } from "react-icons/lu";
import { AiOutlineAlert } from "react-icons/ai";
import { MdOutlineEngineering, MdOutlineSearchOff } from "react-icons/md";
import KeepPng from "../../keep.png";

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
    navigate: "/alerts",
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
    navigate: "/settings?selectedTab=api-key",
  },
];

const EXTERNAL_OPTIONS = [
  {
    icon: FileTextIcon,
    label: "Keep Docs",
    shortcut: ["⇧", "D"],
    navigate: "https://docs.keephq.dev",
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

export const Search = () => {
  const [query, setQuery] = useState<string>("");
  const router = useRouter();
  const comboboxBtnRef = useRef<ElementRef<"button">>(null);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        if (comboboxBtnRef.current) {
          comboboxBtnRef.current.click();
        }
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

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
            <Combobox.Option
              key={option.label}
              as={Fragment}
              value={option.navigate}
            >
              {({ active }) => (
                <ListItem
                  className={`flex items-center justify-start space-x-3 cursor-default select-none p-2 ${
                    active ? "bg-orange-400 text-white" : "text-gray-900"
                  }`}
                >
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
            </Combobox.Option>
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
            <Combobox.Option
              key={option.label}
              as={Fragment}
              value={option.navigate}
            >
              {({ active }) => (
                <ListItem
                  className={`flex items-center justify-start space-x-3 cursor-default select-none p-2 ${
                    active ? "bg-orange-400 text-white" : "text-gray-900"
                  }`}
                >
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
            </Combobox.Option>
          ))}
        </List>
        <List>
          <ListItem className="pl-2">
            <Subtitle>External Sources</Subtitle>
          </ListItem>
          {EXTERNAL_OPTIONS.map((option) => (
            <Combobox.Option
              key={option.label}
              as={Fragment}
              value={option.navigate}
            >
              {({ active }) => (
                <ListItem
                  className={`flex items-center justify-start space-x-3 cursor-default select-none p-2 ${
                    active ? "bg-orange-400 text-white" : "text-gray-900"
                  }`}
                >
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
            </Combobox.Option>
          ))}
        </List>
      </ListItem>
    );
  };

  return (
    <div className="flex items-center space-x-3 py-3 px-2 border-b border-gray-300">
      <Link href="/">
        <Image className="w-8" src={KeepPng} alt="Keep Logo" />
      </Link>

      <Combobox
        defaultValue=""
        onChange={(value) => value && router.push(value)}
        nullable
        as="div"
        className="relative"
      >
        {({ open }) => (
          <>
            {open && (
              <div
                className="fixed inset-0 bg-black/40 z-10"
                aria-hidden="true"
              />
            )}
            <Combobox.Button ref={comboboxBtnRef} aria-disabled={open}>
              <Combobox.Input
                as={TextInput}
                className="z-20"
                placeholder="Search or start with ⌘K"
                color="orange"
                onChange={(event) => setQuery(event.target.value)}
              />
            </Combobox.Button>
            <Transition
              as={Fragment}
              afterLeave={() => setQuery("")}
              leave="transition ease-in duration-100"
              leaveFrom="opacity-100"
              leaveTo="opacity-0"
            >
              <Combobox.Options
                className="absolute mt-1 max-h-screen overflow-auto rounded-md bg-white shadow-lg ring-1 ring-black/5 focus:outline-none z-20 w-96"
                as={List}
              >
                <NoQueriesFoundResult />
                <FilteredResults />
                <DefaultResults />
              </Combobox.Options>
            </Transition>
          </>
        )}
      </Combobox>
    </div>
  );
};
