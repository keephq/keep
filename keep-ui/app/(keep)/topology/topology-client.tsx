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
import { Button } from "@/components/ui";
import { ArrowPathIcon } from "@heroicons/react/24/outline";
import { useApi } from "@/shared/lib/hooks/useApi";
import { pullTopology } from "./api";
import { toast } from "react-toastify";

export function TopologyPageClient({
  applications,
  topologyServices,
}: {
  applications?: TopologyApplication[];
  topologyServices?: TopologyService[];
}) {
  const [tabIndex, setTabIndex] = useState(0);
  const { selectedObjectId } = useContext(TopologySearchContext);
  const api = useApi();

  const handlePullTopology = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await pullTopology(api);
      toast.success("Topology pull initiated");
    } catch (error) {
      toast.error("Failed to pull topology");
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
          icon={() => {
            return (
              <Icon
                icon={ArrowPathIcon}
                className="h-4 w-4 mr-2.5"
                onClick={handlePullTopology}
                tooltip="Pull latest topology"
              />
            );
          }}
        >
          Topology Map
        </Tab>
        <Tab className="items-center">Applications</Tab>
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
