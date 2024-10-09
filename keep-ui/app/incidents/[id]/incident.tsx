"use client";
import Loading from "app/loading";
import { useIncident } from "utils/hooks/useIncidents";
import IncidentInformation from "./incident-info";
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
import IncidentAlerts from "./incident-alerts";
import { useRouter } from "next/navigation";
import IncidentTimeline from "./incident-timeline";
import { CiBellOn, CiChat2, CiViewTimeline } from "react-icons/ci";
import { IoIosGitNetwork } from "react-icons/io";
import IncidentChat from "./incident-chat";
import { Workflows } from "components/icons";
import IncidentWorkflowTable from "./incident-workflow-table";
import { TopologyMap } from "@/app/topology/ui/map";
import { TopologySearchProvider } from "@/app/topology/TopologySearchContext";
import { useState } from "react";
import { FiActivity } from "react-icons/fi";
import IncidentActivity from "./incident-activity";

interface Props {
  incidentId: string;
}

// TODO: generate metadata with incident name
export default function IncidentView({ incidentId }: Props) {
  const { data: incident, isLoading, error } = useIncident(incidentId);
  const [index, setIndex] = useState(0);

  const router = useRouter();

  if (isLoading || !incident) return <Loading />;
  if (error) return <Title>Incident does not exist.</Title>;

  return (
    <>
      <div className="flex justify-between items-center">
        <IncidentInformation incident={incident} />
      </div>
      <Card className="flex flex-col items-center justify-center gap-y-8 mt-10 p-4 relative mx-auto">
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
            className="sticky xl:-top-10 -top-4 bg-white z-10"
          >
            <Tab icon={FiActivity}>
              Activity
              <Badge
                color="green"
                className="ml-1.5 text-xs px-1 py-0.5 -my-0.5 pointer-events-none"
              >
                New
              </Badge>
            </Tab>
            <Tab icon={CiBellOn}>Alerts</Tab>
            <Tab icon={CiViewTimeline}>Timeline</Tab>
            <Tab icon={IoIosGitNetwork}>Topology</Tab>
            <Tab icon={Workflows}>Workflows</Tab>
            <Tab icon={CiChat2}>
              Chat
              <Badge
                color="green"
                className="ml-1.5 text-xs px-1 py-0.5 -my-0.5 pointer-events-none"
              >
                New
              </Badge>
            </Tab>
          </TabList>
          <TabPanels>
            <TabPanel>
              <IncidentActivity incident={incident} />
            </TabPanel>
            <TabPanel>
              <IncidentAlerts incident={incident} />
            </TabPanel>
            <TabPanel>
              <IncidentTimeline incident={incident} />
            </TabPanel>
            <TabPanel className="pt-3 h-[calc(100vh-28rem)]">
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
      </Card>
    </>
  );
}
