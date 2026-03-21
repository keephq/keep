"use client";

import {
  Icon,
  Tab,
  TabGroup,
  TabList,
  TabPanel,
  TabPanels,
} from "@tremor/react";
import { TopologyMap } from "./ui/map";
import { ApplicationsList } from "./ui/applications/applications-list";
import React, { useContext, useEffect, useState } from "react";
import { TopologySearchContext } from "./TopologySearchContext";
import { TopologyApplication, TopologyService } from "./model";
import { ArrowPathIcon } from "@heroicons/react/24/outline";
import { useApi } from "@/shared/lib/hooks/useApi";
import { pullTopology } from "./api";
import { toast } from "react-toastify";
import { useI18n } from "@/i18n/hooks/useI18n";

export function TopologyPageClient({
  applications,
  topologyServices,
}: {
  applications?: TopologyApplication[];
  topologyServices?: TopologyService[];
}) {
  const { t } = useI18n();
  const [tabIndex, setTabIndex] = useState(0);
  const { selectedObjectId } = useContext(TopologySearchContext);
  const api = useApi();

  const handlePullTopology = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await pullTopology(api);
      toast.success(t("topology.messages.pullSuccess"));
    } catch (error) {
      toast.error(t("topology.messages.pullFailed"));
      console.error("Failed to pull topology:", error);
    }
  };

  useEffect(() => {
    if (!selectedObjectId) {
      return;
    }
    setTabIndex(0);
  }, [selectedObjectId]);

  return (
    <TabGroup
      id="topology-tabs"
      className="flex flex-col"
      index={tabIndex}
      onIndexChange={setTabIndex}
    >
      <TabList className="mb-2">
        <Tab
          className="items-center"
        >
          {t("topology.tabs.map")}
        </Tab>
        <Tab className="items-center">{t("topology.applications.title")}</Tab>
        <Tab
          className="items-center"
          icon={ArrowPathIcon}
          onClick={handlePullTopology}
        >
          {t("topology.actions.pullFromProviders")}</Tab>
      </TabList>
      <TabPanels className="flex-1 flex flex-col">
        <TabPanel className="h-[calc(100vh-10rem)]">
          <TopologyMap
            standalone
            topologyApplications={applications}
            topologyServices={topologyServices}
            isVisible={tabIndex === 0}
          />
        </TabPanel>
        <TabPanel className="flex-1">
          <ApplicationsList applications={applications} />
        </TabPanel>
      </TabPanels>
    </TabGroup>
  );
}
