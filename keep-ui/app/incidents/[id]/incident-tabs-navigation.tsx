"use client";

import { FiActivity } from "react-icons/fi";
import { CiBellOn, CiChat2, CiViewTimeline } from "react-icons/ci";
import { IoIosGitNetwork } from "react-icons/io";
import { Workflows } from "components/icons";
import { useParams, usePathname } from "next/navigation";
import { TabLinkNavigation, TabNavigationLink } from "@/shared/ui";
import { RectangleStackIcon } from "@heroicons/react/24/outline";

export const tabs = [
  { icon: CiBellOn, label: "Alerts", path: "alerts" },
  { icon: FiActivity, label: "Activity", path: "activity" },
  { icon: CiViewTimeline, label: "Timeline", path: "timeline" },
  {
    icon: IoIosGitNetwork,
    label: "Topology",
    path: "topology",
  },
  { icon: Workflows, label: "Workflows", path: "workflows" },
  { icon: RectangleStackIcon, label: "Similar incidents", path: "similar" },
  { icon: CiChat2, label: "Chat", path: "chat" },
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
        >
          {tab.label}
        </TabNavigationLink>
      ))}
    </TabLinkNavigation>
  );
}
