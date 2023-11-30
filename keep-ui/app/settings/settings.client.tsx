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
import { useState } from "react";

export default function SettingsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams()!;
  const pathname = usePathname();
  const [selectedTab, setSelectedTab] = useState<string>(
    searchParams?.get("selectedTab") || "users"
  );

  const handleTabChange = (tab: string) => {
    setSelectedTab(tab);
    router.push(`${pathname}?selectedTab=${tab}`);
  };

  // TODO: more robust way to handle this
  const tabIndex =
    selectedTab === "users"
      ? 0
      : selectedTab === "webhook"
      ? 1
      : selectedTab === "smtp"
      ? 2
      : 3;

  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") router.push("/signin");

  /**
   * TODO: Refactor this page to use pages
   * Right now we load all components at once when we load the main settings page.
   * It should be /settings/users and /settings/webhook, etc.
   * Think about a proper way to implement it.
   */
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
