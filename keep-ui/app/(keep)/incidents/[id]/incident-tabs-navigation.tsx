"use client";

import { IoIosGitNetwork } from "react-icons/io";
import { Workflows } from "components/icons";
import { useParams, usePathname } from "next/navigation";
import { TabLinkNavigation, TabNavigationLink } from "@/shared/ui";
import { BellAlertIcon, BoltIcon } from "@heroicons/react/24/outline";
import { CiViewTimeline } from "react-icons/ci";
import { IncidentDto } from "@/entities/incidents/model";
import { useAlertsByRunID, useIncident, useIncidentAlerts } from "@/utils/hooks/useIncidents";

export const tabs = [
  { icon: BellAlertIcon, label: "Alerts", path: "alerts", prefetch: true },
  { icon: CiViewTimeline, label: "Alerts by Run", path: "alerts-by-run", prefetch: true },
  // { icon: CiViewTimeline, label: "Timeline", path: "timeline" },
  // {
  //   icon: IoIosGitNetwork,
  //   label: "Topology",
  //   path: "topology",
  // },
  // { icon: Workflows, label: "Workflows", path: "workflows" },
];

export function IncidentTabsNavigation() {
  // Using type assertion because this component only renders on the /incidents/[id] routes
  const { id } = useParams<{ id: string }>() as { id: string };
  const pathname = usePathname();
  const { data: alerts } = useIncidentAlerts(id);
  const { data: alerts_by_run } = useAlertsByRunID(id);

  return (
    <TabLinkNavigation className="sticky xl:-top-10 -top-4 bg-tremor-background-muted">
      {tabs.map((tab) => (
        <TabNavigationLink
          key={tab.path}
          icon={tab.icon}
          isActive={pathname?.endsWith(tab.path)}
          href={`/incidents/${id}/${tab.path}`}
          prefetch={!!tab.prefetch}
          count={tab.path === "alerts" ? alerts?.count : tab.path === "alerts-by-run" ? alerts_by_run?.count : undefined}
        >
          {tab.label}
        </TabNavigationLink>
      ))}
    </TabLinkNavigation>
  );
}
