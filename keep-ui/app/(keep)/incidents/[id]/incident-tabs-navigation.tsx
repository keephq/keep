"use client";

import { IoIosGitNetwork } from "react-icons/io";
import { Workflows } from "components/icons";
import { useParams, usePathname } from "next/navigation";
import { TabLinkNavigation, TabNavigationLink } from "@/shared/ui";
import { BellAlertIcon, BoltIcon } from "@heroicons/react/24/outline";
import { CiViewTimeline } from "react-icons/ci";
import { IncidentDto } from "@/entities/incidents/model";
import { useIncident } from "@/utils/hooks/useIncidents";

export const tabs = [
  { icon: BellAlertIcon, label: "Alerts", path: "alerts" },
  { icon: BoltIcon, label: "Activity", path: "activity", prefetch: true },
  { icon: CiViewTimeline, label: "Timeline", path: "timeline" },
  {
    icon: IoIosGitNetwork,
    label: "Topology",
    path: "topology",
  },
  { icon: Workflows, label: "Workflows", path: "workflows" },
];

export function IncidentTabsNavigation({
  incident: initialIncidentData,
}: {
  incident?: IncidentDto;
}) {
  // Using type assertion because this component only renders on the /incidents/[id] routes
  const { id } = useParams<{ id: string }>() as { id: string };
  const { data: incident } = useIncident(id, {
    fallbackData: initialIncidentData,
  });
  const pathname = usePathname();
  return (
    <TabLinkNavigation className="sticky xl:-top-10 -top-4 bg-tremor-background-muted z-10">
      {tabs.map((tab) => (
        <TabNavigationLink
          key={tab.path}
          icon={tab.icon}
          isActive={pathname?.endsWith(tab.path)}
          href={`/incidents/${id}/${tab.path}`}
          prefetch={!!tab.prefetch}
          count={tab.path === "alerts" ? incident?.alerts_count : undefined}
        >
          {tab.label}
        </TabNavigationLink>
      ))}
    </TabLinkNavigation>
  );
}
