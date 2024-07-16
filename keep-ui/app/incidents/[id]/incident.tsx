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

interface Props {
  incidentId: string;
}

export default function IncidentView({ incidentId }: Props) {
  const { data: incident, isLoading, error } = useIncident(incidentId);
  const router = useRouter();

  if (isLoading) {
    <Loading />;
  }

  if (error || !incident) {
    return <Title>Incident does not exist.</Title>;
  }

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
      <Card className="flex flex-col items-center justify-center gap-y-8 mt-10 p-4 md:p-10 mx-auto">
        <div className="w-full">
          <div className="flex divide-x p-2">
            <div id="incidentOverview" className="w-2/5 min-w-[400px] pr-2.5">
              <IncidentInformation incident={incident} />
            </div>
            <div id="incidentTabs" className="w-full pl-2.5 overflow-x-scroll">
              <TabGroup defaultIndex={0}>
                <TabList variant="line" color="orange">
                  <Tab>Alerts</Tab>
                  <Tab>Timeline</Tab>
                  <Tab>Topology</Tab>
                </TabList>
                <TabPanels>
                  <TabPanel>
                    <IncidentAlerts
                      incidentFingerprint={incident.id}
                    />
                  </TabPanel>
                  <TabPanel>Coming Soon...</TabPanel>
                  <TabPanel>Coming Soon...</TabPanel>
                </TabPanels>
              </TabGroup>
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}
