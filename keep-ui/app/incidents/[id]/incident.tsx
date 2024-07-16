"use client";
import Loading from "app/loading";
import { useIncident } from "utils/hooks/useIncidents";
import IncidentInformation from "./incident-info";
import {
  Tab,
  TabGroup,
  TabList,
  TabPanel,
  TabPanels,
  Title,
} from "@tremor/react";
import IncidentAlerts from "./incident-alerts";
import IncidentTopology from "./incident-topology";

interface Props {
  incidentId: string;
}

export default function IncidentView({ incidentId }: Props) {
  const { data: incident, isLoading, error } = useIncident(incidentId);

  if (isLoading) {
    <Loading />;
  }

  if (error || !incident) {
    return <Title>Incident does not exist.</Title>;
  }

  return (
    <div className="w-full">
      <div className="flex divide-x p-2">
        <div id="incidentOverview" className="w-2/5 pr-2.5">
          <IncidentInformation incident={incident} />
        </div>
        <div id="incidentTabs" className="w-full pl-2.5">
          <TabGroup defaultIndex={0}>
            <TabList variant="line" color="orange">
              <Tab>Alerts</Tab>
              <Tab>Timeline</Tab>
              <Tab>Topology</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <IncidentAlerts
                  incidentFingerprint={incident.incident_fingerprint}
                />
              </TabPanel>
              <TabPanel>Coming Soon...</TabPanel>
              <TabPanel>
                <IncidentTopology />
              </TabPanel>
            </TabPanels>
          </TabGroup>
        </div>
      </div>
    </div>
  );
}
