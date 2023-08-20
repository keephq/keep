"use client";
import { Tab, TabGroup, TabList, TabPanel, TabPanels } from "@tremor/react";
import UnderConstruction from "../under-construction";
import { GlobeAltIcon, UserGroupIcon } from "@heroicons/react/24/outline";

export default function SettingsPage() {
  return (
    <TabGroup>
      <TabList>
        <Tab icon={UserGroupIcon}>Users</Tab>
        <Tab icon={GlobeAltIcon}>Webhook</Tab>
      </TabList>
      <TabPanels>
        <TabPanel>
          <UnderConstruction />
        </TabPanel>
        <TabPanel>
          <UnderConstruction />
        </TabPanel>
      </TabPanels>
    </TabGroup>
  );
}
