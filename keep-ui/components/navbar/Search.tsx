"use client";

import { ElementRef, Fragment, useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Icon, List, ListItem, Subtitle } from "@tremor/react";
import {
  Combobox,
  ComboboxButton,
  ComboboxInput,
  ComboboxOption,
  ComboboxOptions,
  Popover,
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
} from "@heroicons/react/24/outline";
import { VscDebugDisconnect } from "react-icons/vsc";
import { LuWorkflow } from "react-icons/lu";
import { AiOutlineAlert, AiOutlineGroup } from "react-icons/ai";
import { MdOutlineEngineering, MdOutlineSearchOff } from "react-icons/md";
import { useConfig } from "utils/hooks/useConfig";
import { Session } from "next-auth";
import { signIn } from "next-auth/react";
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
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const router = useRouter();
  const comboboxBtnRef = useRef<ElementRef<"button">>(null);
  const comboboxInputRef = useRef<ElementRef<"input">>(null);
  const { data: configData } = useConfig();
  const docsUrl = configData?.KEEP_DOCS_URL || "https://docs.keephq.dev";
  const [isLoading, setIsLoading] = useState(false);

  // Log session for debugging
  useEffect(() => {
    console.log("Search component session:", session);
  }, [session]);

  const EXTERNAL_OPTIONS = [
    {
      icon: FileTextIcon,
      label: "Keep Docs",
      shortcut: ["⇧", "D"],
      navigate: docsUrl,
    },
    // Rest of your external options...
  ];

  const OPTIONS = [...NAVIGATION_OPTIONS, ...EXTERNAL_OPTIONS];

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

  // Tenant switcher function
  const switchTenant = async (tenantId: string) => {
    setIsLoading(true);
    try {
      // Use the tenant-switch provider to change tenants
      let sessionAsJson = JSON.stringify(session);
      const result = await signIn("tenant-switch", {
        redirect: false,
        tenantId,
        sessionAsJson,
      });

      if (result?.error) {
        console.error("Error switching tenant:", result.error);
      } else {
        // new tenant, let's reload the page
        window.location.reload();
      }
    } catch (error) {
      console.error("Error switching tenant:", error);
    } finally {
      setIsLoading(false);
    }
  };

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

  // Check if tenant switching is available - with null/undefined check safety
  const hasTenantSwitcher =
    session &&
    session.user &&
    session.user.tenantIds &&
    session.user.tenantIds.length > 1;

  // Get current tenant logo URL if available
  const currentTenant = session?.user?.tenantIds?.find(
    (tenant) => tenant.tenant_id === session.tenantId
  );
  const tenantLogoUrl = currentTenant?.tenant_logo_url;

  return (
    <div className="flex items-center w-full py-3 px-2 border-b border-gray-300">
      <div className="flex-shrink-0 flex items-center">
        {hasTenantSwitcher ? (
          <Popover className="relative">
            {({ open }) => (
              <>
                <Popover.Button
                  className="focus:outline-none flex items-center"
                  disabled={isLoading}
                >
                  <Image className="w-8" src={KeepPng} alt="Keep Logo" />
                  {tenantLogoUrl && (
                    <Image
                      src={tenantLogoUrl}
                      alt={`${currentTenant?.tenant_name || "Tenant"} Logo`}
                      width={60}
                      height={60}
                      className="ml-4 object-cover"
                    />
                  )}
                </Popover.Button>

                <Popover.Panel className="absolute z-10 mt-1 w-48 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                  <div className="py-1 divide-y divide-gray-200">
                    <div className="px-3 py-2 text-xs font-medium text-gray-500">
                      Switch Tenant
                    </div>
                    {session.user.tenantIds?.map((tenant) => (
                      <button
                        key={tenant.tenant_id}
                        className={`block w-full text-left px-4 py-2 text-sm ${
                          tenant.tenant_id === session.tenantId
                            ? "bg-orange-50 text-orange-700 font-medium"
                            : "text-gray-700 hover:bg-gray-50"
                        }`}
                        onClick={() => switchTenant(tenant.tenant_id)}
                        disabled={
                          tenant.tenant_id === session.tenantId || isLoading
                        }
                      >
                        {tenant.tenant_name}
                      </button>
                    ))}
                  </div>
                </Popover.Panel>
              </>
            )}
          </Popover>
        ) : (
          <Link href="/">
            <Image className="w-8" src={KeepPng} alt="Keep Logo" />
          </Link>
        )}
      </div>

      <div className="flex-grow ml-4">
        <Combobox
          value={query}
          onChange={onOptionSelection}
          as="div"
          className="relative w-full"
        >
          {({ open }) => (
            <>
              {open && (
                <div
                  className="fixed inset-0 bg-black/40 z-10"
                  aria-hidden="true"
                />
              )}
              <ComboboxButton ref={comboboxBtnRef} className="w-full">
                <ComboboxInput
                  className="z-20 tremor-TextInput-root relative flex items-center w-full outline-none rounded-tremor-default transition duration-100 border shadow-tremor-input dark:shadow-dark-tremor-input bg-tremor-background dark:bg-dark-tremor-background hover:bg-tremor-background-muted dark:hover:bg-dark-tremor-background-muted text-tremor-content dark:text-dark-tremor-content border-tremor-border dark:border-dark-tremor-border tremor-TextInput-input bg-transparent focus:outline-none focus:ring-0 text-tremor-default py-2 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none pr-3 pl-3 placeholder:text-tremor-content dark:placeholder:text-dark-tremor-content"
                  placeholder={placeholderText}
                  color="orange"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  ref={comboboxInputRef}
                />
              </ComboboxButton>
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
    </div>
  );
};
