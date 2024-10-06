"use client";

import { Tab, TabGroup, TabList, TabPanel, TabPanels } from "@tremor/react";
import { TopologyMap } from "./ui/map";
import { ApplicationsList } from "./ui/applications/applications-list";
import { useContext, useEffect, useState } from "react";
import { TopologySearchContext } from "./TopologySearchContext";
import { TopologyApplication, TopologyService } from "./model";

export function TopologyPageClient({
  applications,
  topologyServices,
}: {
  applications?: TopologyApplication[];
  topologyServices?: TopologyService[];
}) {
  const [tabIndex, setTabIndex] = useState(0);
  const { selectedObjectId } = useContext(TopologySearchContext);

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
        <Tab>Topology Map</Tab>
        <Tab>Applications</Tab>
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
