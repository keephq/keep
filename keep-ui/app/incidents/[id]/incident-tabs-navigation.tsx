"use client";

import { IoIosGitNetwork } from "react-icons/io";
import { Workflows } from "components/icons";
import { useParams, usePathname } from "next/navigation";
import { TabLinkNavigation, TabNavigationLink } from "@/shared/ui";
import {
  BellAlertIcon,
  BoltIcon,
  RectangleStackIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";
import { CiViewTimeline } from "react-icons/ci";

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
  { icon: RectangleStackIcon, label: "Similar incidents", path: "similar" },
  { icon: SparklesIcon, label: "Chat with AI", path: "chat" },
];

export function IncidentTabsNavigation() {
  // Using type assertion because this component only renders on the /incidents/[id] routes
  const { id } = useParams<{ id: string }>() as { id: string };
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
        >
          {tab.label}
        </TabNavigationLink>
      ))}
    </TabLinkNavigation>
  );
}
