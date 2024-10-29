"use client";
import { useState } from "react";
import { FiActivity } from "react-icons/fi";
import {
  Badge,
  Card,
  Tab,
  TabGroup,
  TabList,
  TabPanel,
  TabPanels,
  Title,
} from "@tremor/react";
import { CiBellOn, CiChat2, CiViewTimeline } from "react-icons/ci";
import { IoIosGitNetwork } from "react-icons/io";
import { Workflows } from "components/icons";
import { useIncident } from "utils/hooks/useIncidents";
import { TopologyMap } from "@/app/topology/ui/map";
import { TopologySearchProvider } from "@/app/topology/TopologySearchContext";
import Loading from "app/loading";
import IncidentWorkflowTable from "./incident-workflow-table";
import IncidentOverview from "./incident-overview";
import IncidentAlerts from "./incident-alerts";
import IncidentTimeline from "./incident-timeline";
import IncidentChat from "./incident-chat";
import IncidentActivity from "./incident-activity";
import { IncidentHeader } from "./incident-header";

interface Props {
  incidentId: string;
}

// TODO: generate metadata with incident name
export default function IncidentView({ incidentId }: Props) {
  const { data: incident, mutate, isLoading, error } = useIncident(incidentId);
  const [index, setIndex] = useState(0);

  if (isLoading || !incident) return <Loading />;
  if (error) return <Title>Incident does not exist.</Title>;

  return (
    <div className="flex flex-col gap-2">
      <IncidentHeader incident={incident} mutate={mutate} />
      <TabGroup
        id="incidentTabs"
        index={index}
        defaultIndex={0}
        onIndexChange={setIndex}
      >
        {/* Compensating for page-container padding, TODO: more robust solution  */}
        <TabList
          variant="line"
          color="orange"
          className="sticky xl:-top-10 -top-4 bg-tremor-background-muted z-10"
        >
          <Tab icon={CiBellOn}>Overview and Alerts</Tab>
          <Tab icon={FiActivity}>
            Activity
            <Badge
              color="green"
              className="ml-1.5 text-xs px-1 py-0.5 -my-0.5 pointer-events-none"
            >
              New
            </Badge>
          </Tab>
          <Tab icon={CiViewTimeline}>Timeline</Tab>
          <Tab icon={IoIosGitNetwork}>Topology</Tab>
          <Tab icon={Workflows}>Workflows</Tab>
          <Tab icon={CiChat2}>Chat</Tab>
        </TabList>
        <TabPanels>
          <TabPanel>
            <Card className="mb-4">
              <IncidentOverview incident={incident} />
            </Card>
            <IncidentAlerts incident={incident} />
          </TabPanel>
          <TabPanel>
            <Card>
              <IncidentActivity incident={incident} />
            </Card>
          </TabPanel>
          <TabPanel>
            <IncidentTimeline incident={incident} />
          </TabPanel>
          <TabPanel className="pt-3 h-[calc(100vh-12rem)]">
            <TopologySearchProvider>
              <TopologyMap
                services={incident.services}
                isVisible={index === 2}
              />
            </TopologySearchProvider>
          </TabPanel>
          <TabPanel>
            <IncidentWorkflowTable incident={incident} />
          </TabPanel>
          <TabPanel>
            <IncidentChat incident={incident} />
          </TabPanel>
        </TabPanels>
      </TabGroup>
    </div>
  );
}
