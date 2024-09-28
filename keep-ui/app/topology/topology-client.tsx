"use client";

import { Tab, TabGroup, TabList, TabPanel, TabPanels } from "@tremor/react";
import { TopologyMap } from "./ui/map";
import { ApplicationsList } from "./ui/applications/applications-list";
import { useContext, useEffect, useState } from "react";
import { ServiceSearchContext } from "./service-search-context";
import { TopologyApplication, TopologyService } from "./models";

export function TopologyPageClient({
  applications,
  topologyServices,
}: {
  applications?: TopologyApplication[];
  topologyServices?: TopologyService[];
}) {
  const [tabIndex, setTabIndex] = useState(0);
  const { selectedServiceId } = useContext(ServiceSearchContext);

  useEffect(() => {
    if (!selectedServiceId) {
      return;
    }
    setTabIndex(0);
  }, [selectedServiceId]);

  return (
    <TabGroup
      id="topology-tabs"
      className="h-[calc(100%-7rem)] flex flex-col"
      index={tabIndex}
      onIndexChange={setTabIndex}
    >
      <TabList className="mb-2">
        <Tab>Topology Map</Tab>
        <Tab>Applications</Tab>
      </TabList>
      <TabPanels className="flex-1 flex flex-col">
        <TabPanel className="flex-1">
          <TopologyMap
            topologyApplications={applications}
            topologyServices={topologyServices}
          />
        </TabPanel>
        <TabPanel className="flex-1">
          <ApplicationsList applications={applications} />
        </TabPanel>
      </TabPanels>
    </TabGroup>
  );
}
