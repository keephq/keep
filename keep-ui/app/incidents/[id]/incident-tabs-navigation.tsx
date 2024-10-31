"use client";

import { FiActivity } from "react-icons/fi";
import { CiBellOn, CiChat2, CiViewTimeline } from "react-icons/ci";
import { IoIosGitNetwork } from "react-icons/io";
import { Workflows } from "components/icons";
import { useParams, usePathname } from "next/navigation";
import {
  TabNavigation,
  TabNavigationLink,
} from "@/shared/ui/TabLinkNavigation";

export const tabs = [
  { icon: CiBellOn, label: "Overview and Alerts", path: "alerts" },
  { icon: FiActivity, label: "Activity", path: "activity" },
  { icon: CiViewTimeline, label: "Timeline", path: "timeline" },
  {
    icon: IoIosGitNetwork,
    label: "Topology",
    path: "topology",
  },
  { icon: Workflows, label: "Workflows", path: "workflows" },
  { icon: CiChat2, label: "Chat", path: "chat" },
];

export function IncidentTabsNavigation() {
  // Using type assertion because this component only renders on the /incidents/[id] routes
  const { id } = useParams<{ id: string }>() as { id: string };
  const pathname = usePathname();
  return (
    <TabNavigation className="sticky xl:-top-10 -top-4 bg-tremor-background-muted z-10">
      {tabs.map((tab) => (
        <TabNavigationLink
          key={tab.path}
          icon={tab.icon}
          isActive={pathname?.endsWith(tab.path)}
          href={`/incidents/${id}/${tab.path}`}
        >
          {tab.label}
        </TabNavigationLink>
      ))}
    </TabNavigation>
  );
}
