"use client";
import { Tab, TabGroup, TabList, TabPanel, TabPanels } from "@tremor/react";
import {
  GlobeAltIcon,
  UserGroupIcon,
  EnvelopeIcon,
  KeyIcon,
} from "@heroicons/react/24/outline";
import UsersSettings from "./users-settings";
import WebhookSettings from "./webhook-settings";
import APIKeySettings from "./api-key-settings";
import { useSession } from "next-auth/react";
import Loading from "app/loading";
import SmtpSettings from "./smtp-settings";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function SettingsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams()!;
  const pathname = usePathname();
  const [selectedTab, setSelectedTab] = useState<string>(
    searchParams?.get("selectedTab") || "users"
  );
  const [tabIndex, setTabIndex] = useState<number>(0);

  const handleTabChange = useCallback(
    (tab: string) => {
      if (tab !== selectedTab) {
        router.replace(`${pathname}?selectedTab=${tab}`);
        setSelectedTab(tab);
      }
    },
    [pathname, router, selectedTab]
  );

  // useEffect(() => {
  //   const newSelectedTab = searchParams?.get("selectedTab") || selectedTab;
  //   handleTabChange(newSelectedTab);
  // }, [searchParams, handleTabChange, selectedTab]);

  // TODO: more robust way to handle this
  useEffect(() => {
    const newSelectedTab = searchParams?.get("selectedTab") || "users";
    const tabIndex =
      newSelectedTab === "users"
        ? 0
        : newSelectedTab === "webhook"
        ? 1
        : newSelectedTab === "smtp"
        ? 2
        : 3;
    setTabIndex(tabIndex);
    setSelectedTab(newSelectedTab);
  }, [searchParams]);

  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") router.push("/signin");

  return (
    <TabGroup index={tabIndex}>
      <TabList color="orange">
        <Tab icon={UserGroupIcon} onClick={() => handleTabChange("users")}>
          Users
        </Tab>
        <Tab icon={GlobeAltIcon} onClick={() => handleTabChange("webhook")}>
          Webhook
        </Tab>
        <Tab icon={EnvelopeIcon} onClick={() => handleTabChange("smtp")}>
          SMTP
        </Tab>
        <Tab icon={KeyIcon} onClick={() => handleTabChange("api-key")}>
          API Key
        </Tab>
      </TabList>
      <TabPanels>
        <TabPanel>
          <UsersSettings
            accessToken={session?.accessToken!}
            currentUser={session?.user}
            selectedTab={selectedTab}
          />
        </TabPanel>
        <TabPanel>
          <WebhookSettings
            accessToken={session?.accessToken!}
            selectedTab={selectedTab}
          />
        </TabPanel>
        <TabPanel>
          <SmtpSettings
            accessToken={session?.accessToken!}
            selectedTab={selectedTab}
          />
        </TabPanel>
        <TabPanel>
          <APIKeySettings
            accessToken={session?.accessToken!}
            selectedTab={selectedTab}
          />
        </TabPanel>
      </TabPanels>
    </TabGroup>
  );
}
