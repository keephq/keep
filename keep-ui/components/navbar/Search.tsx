"use client";

import { ElementRef, Fragment, useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Icon, List, ListItem, Subtitle } from "@tremor/react";
import {
  Combobox,
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
import { useI18n } from "@/i18n/hooks/useI18n";

const NAVIGATION_OPTIONS = [
  {
    icon: VscDebugDisconnect,
    labelKey: "nav.searchMenu.goToProviders",
    shortcut: ["p"],
    navigate: "/providers",
  },
  {
    icon: AiOutlineAlert,
    labelKey: "nav.searchMenu.goToAlertConsole",
    shortcut: ["g"],
    navigate: "/alerts/feed",
  },
  {
    icon: AiOutlineGroup,
    labelKey: "nav.searchMenu.goToAlertQuality",
    shortcut: ["q"],
    navigate: "/alerts/quality",
  },
  {
    icon: MdOutlineEngineering,
    labelKey: "nav.searchMenu.goToAlertGroups",
    shortcut: ["g"],
    navigate: "/rules",
  },
  {
    icon: LuWorkflow,
    labelKey: "nav.searchMenu.goToWorkflows",
    shortcut: ["wf"],
    navigate: "/workflows",
  },
  {
    icon: UserGroupIcon,
    labelKey: "nav.searchMenu.goToUsersManagement",
    shortcut: ["u"],
    navigate: "/settings?selectedTab=users",
  },
  {
    icon: GlobeAltIcon,
    labelKey: "nav.searchMenu.goToGenericWebhook",
    shortcut: ["w"],
    navigate: "/settings?selectedTab=webhook",
  },
  {
    icon: EnvelopeIcon,
    labelKey: "nav.searchMenu.goToSMTPSettings",
    shortcut: ["s"],
    navigate: "/settings?selectedTab=smtp",
  },
  {
    icon: KeyIcon,
    labelKey: "nav.searchMenu.goToAPIKey",
    shortcut: ["a"],
    navigate: "/settings?selectedTab=users&userSubTab=api-keys",
  },
];

interface SearchProps {
  session: Session | null;
}

export const Search = ({ session }: SearchProps) => {
  const { t } = useI18n();
  const [query, setQuery] = useState<string>("");
  const [, setSelectedOption] = useState<string | null>(null);
  const router = useRouter();
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
      labelKey: "nav.searchMenu.keepDocs",
      shortcut: ["⇧", "D"],
      navigate: docsUrl,
    },
    {
      icon: GitHubLogoIcon,
      labelKey: "nav.searchMenu.keepSourceCode",
      shortcut: ["⇧", "C"],
      navigate: "https://github.com/keephq/keep",
    },
    {
      icon: TwitterLogoIcon,
      labelKey: "nav.searchMenu.keepTwitter",
      shortcut: ["⇧", "T"],
      navigate: "https://twitter.com/keepalerting",
    },
  ];

  const OPTIONS = [...NAVIGATION_OPTIONS, ...EXTERNAL_OPTIONS].map(option => ({
    ...option,
    label: t(option.labelKey)
  }));

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
          {t("nav.searchMenu.nothingFound")}
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
            <Subtitle>{t("nav.searchMenu.navigate")}</Subtitle>
          </ListItem>
          {NAVIGATION_OPTIONS.map((option) => (
            <ComboboxOption
              key={option.labelKey}
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
                  <span className="text-left">{t(option.labelKey)}</span>
                </ListItem>
              )}
            </ComboboxOption>
          ))}
        </List>
        <List>
          <ListItem className="pl-2">
            <Subtitle>{t("nav.searchMenu.externalSources")}</Subtitle>
          </ListItem>
          {EXTERNAL_OPTIONS.map((option) => (
            <ComboboxOption
              key={option.labelKey}
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
                  <span className="text-left">{t(option.labelKey)}</span>
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

  const [placeholderText, setPlaceholderText] = useState("");

  // Using effect to avoid mismatch on hydration. TODO: context provider for user agent
  useEffect(function updatePlaceholderText() {
    if (!isMac()) {
      setPlaceholderText(t("nav.searchMenu.placeholder"));
    } else {
      setPlaceholderText(t("nav.searchMenu.placeholderWithShortcut"));
    }
  }, [t]);

  // Check if tenant switching is available - with null/undefined check safety
  const hasTenantSwitcher =
    session &&
    session.user &&
    session.user.tenantIds &&
    session.user.tenantIds.length > 1;

  // Get current tenant logo URL if available - this now works even with just one tenant
  const currentTenant = session?.user?.tenantIds?.find(
    (tenant) => tenant.tenant_id === session.tenantId
  );
  const tenantLogoUrl = currentTenant?.tenant_logo_url;
  const hasTenantLogo = Boolean(tenantLogoUrl);

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
                      src={tenantLogoUrl || ""}
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
                      {t("nav.searchMenu.switchTenant")}
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
          <Link href="/" className="flex items-center">
            <Image className="w-8" src={KeepPng} alt="Keep Logo" />
            {hasTenantLogo && (
              <Image
                src={tenantLogoUrl || ""}
                alt={`${currentTenant?.tenant_name || "Tenant"} Logo`}
                width={60}
                height={60}
                className="ml-4 object-cover"
              />
            )}
          </Link>
        )}
      </div>

      <div className="flex-grow ml-4">
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

              <ComboboxInput
                className="z-20 tremor-TextInput-root relative flex items-center w-full outline-none rounded-tremor-default transition duration-100 border shadow-tremor-input dark:shadow-dark-tremor-input bg-tremor-background dark:bg-dark-tremor-background hover:bg-tremor-background-muted dark:hover:bg-dark-tremor-background-muted text-tremor-content dark:text-dark-tremor-content border-tremor-border dark:border-dark-tremor-border tremor-TextInput-input bg-transparent focus:outline-none focus:ring-0 text-tremor-default py-2 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none pr-3 pl-3 placeholder:text-tremor-content dark:placeholder:text-dark-tremor-content"
                placeholder={placeholderText}
                color="orange"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                ref={comboboxInputRef}
              />

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
