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
import { useState } from "react";
import IncidentTimeline from "./incident-timeline";
import { CiBellOn, CiViewTimeline } from "react-icons/ci";
import { IoIosGitNetwork } from "react-icons/io";

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
              className="w-full xl:pl-2.5 overflow-x-scroll"
            >
              <TabGroup defaultIndex={0}>
                <TabList variant="line" color="orange">
                  <Tab icon={CiBellOn}>Alerts</Tab>
                  <Tab icon={CiViewTimeline}>Timeline</Tab>
                  <Tab icon={IoIosGitNetwork}>Topology</Tab>
                </TabList>
                <TabPanels>
                  <TabPanel>
                    <IncidentAlerts incident={incident} />
                  </TabPanel>
                  <TabPanel>
                    <IncidentTimeline incident={incident} />
                  </TabPanel>
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
