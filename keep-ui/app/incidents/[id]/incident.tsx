"use client";
import Loading from "app/loading";
import { useIncident } from "utils/hooks/useIncidents";
import IncidentInformation from "./incident-info";
import {
  Card,
  Icon,
  Subtitle,
  Tab,
  TabGroup,
  TabList,
  TabPanel,
  TabPanels,
  Title,
} from "@tremor/react";
import IncidentAlerts from "./incident-alerts";
import { ArrowUturnLeftIcon } from "@heroicons/react/24/outline";
import { useRouter } from "next/navigation";
import IncidentTimeline from "./incident-timeline";
import { CiBellOn, CiChat2, CiViewTimeline } from "react-icons/ci";
import { IoIosGitNetwork } from "react-icons/io";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import IncidentChat from "./incident-chat";

interface Props {
  incidentId: string;
}

export default function IncidentView({ incidentId }: Props) {
  const { data: incident, isLoading, error } = useIncident(incidentId);

  const router = useRouter();

  if (isLoading || !incident) return <Loading />;
  if (error) return <Title>Incident does not exist.</Title>;

  return (
    <>
      <div className="flex justify-between items-center">
        <div>
          <Title>Incident Management</Title>
          <Subtitle>
            Understand, manage and triage your incidents faster with Keep.
          </Subtitle>
        </div>
        <Icon
          icon={ArrowUturnLeftIcon}
          tooltip="Go Back"
          variant="shadow"
          className="cursor-pointer"
          onClick={() => router.back()}
        />
      </div>
      <Card className="flex flex-col items-center justify-center gap-y-8 mt-10 p-4 md:p-10 mx-auto h-[calc(100vh-180px)]">
        <div className="w-full h-full">
          <div className="flex flex-col gap-2 xl:gap-0 xl:divide-y p-2 h-full">
            <div id="incidentOverview" className="mb-2.5">
              <IncidentInformation incident={incident} />
            </div>
            <div
              id="incidentTabs"
              className="w-full xl:pl-2.5 overflow-x-scroll h-full overflow-hidden"
            >
              <TabGroup defaultIndex={0} className="h-full">
                <TabList variant="line" color="orange">
                  <Tab icon={CiBellOn}>Alerts</Tab>
                  <Tab icon={CiViewTimeline}>Timeline</Tab>
                  <Tab icon={IoIosGitNetwork}>Topology</Tab>
                  <Tab icon={CiChat2}>Chat</Tab>
                </TabList>
                <TabPanels className="h-full">
                  <TabPanel>
                    <IncidentAlerts incident={incident} />
                  </TabPanel>
                  <TabPanel>
                    <IncidentTimeline incident={incident} />
                  </TabPanel>
                  <TabPanel>
                    <div className="h-80">
                      <EmptyStateCard
                        title="Coming Soon..."
                        description="Topology view of the incident is coming soon."
                        buttonText="Go to Topology"
                        onClick={() => router.push("/topology")}
                      />
                    </div>
                  </TabPanel>
                  <TabPanel className="h-[calc(100%-50px)]">
                    <IncidentChat incident={incident} />
                  </TabPanel>
                </TabPanels>
              </TabGroup>
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}
