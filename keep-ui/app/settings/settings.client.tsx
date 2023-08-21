"use client";
import { Tab, TabGroup, TabList, TabPanel, TabPanels } from "@tremor/react";
import { GlobeAltIcon, UserGroupIcon } from "@heroicons/react/24/outline";
import { UsersSettings } from "./users-settings";
import { WebhookSettings } from "./webhook-settings";

export default function SettingsPage() {
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
      </TabList>
      <TabPanels>
        <TabPanel>
          <UsersSettings />
        </TabPanel>
        <TabPanel>
          <WebhookSettings />
        </TabPanel>
      </TabPanels>
    </TabGroup>
  );
}
