"use client";
import { Tab, TabGroup, TabList, TabPanel, TabPanels } from "@tremor/react";
import {
  GlobeAltIcon,
  UserGroupIcon,
  EnvelopeIcon,
  KeyIcon
} from "@heroicons/react/24/outline";
import UsersSettings from "./users-settings";
import WebhookSettings from "./webhook-settings";
import APIKeySettings from "./api-key-settings";
import { useSession } from "next-auth/react"
import Loading from "app/loading";
import SmtpSettings from "./smtp-settings";
import { useRouter } from "next/navigation";

export default function SettingsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") router.push("/signin");

  /**
   * TODO: Refactor this page to use pages
   * Right now we load all components at once when we load the main settings page.
   * It should be /settings/users and /settings/webhook, etc.
   * Think about a proper way to implement it.
   */
  return (
    <TabGroup>
      <TabList color="orange">
        <Tab icon={UserGroupIcon}>Users</Tab>
        <Tab icon={GlobeAltIcon}>Webhook</Tab>
        <Tab icon={EnvelopeIcon}>SMTP</Tab>
        <Tab icon={KeyIcon}>Api Key</Tab>
      </TabList>
      <TabPanels>
        <TabPanel>
          <UsersSettings
            accessToken={session?.accessToken!}
            currentUser={session?.user}
          />
        </TabPanel>
        <TabPanel>
          <WebhookSettings accessToken={session?.accessToken!} />
        </TabPanel>
        <TabPanel>
          <SmtpSettings accessToken={session?.accessToken!} />
        </TabPanel>
        <TabPanel>
          <APIKeySettings accessToken={session?.accessToken!} />
        </TabPanel>
      </TabPanels>
    </TabGroup>
  );
}
