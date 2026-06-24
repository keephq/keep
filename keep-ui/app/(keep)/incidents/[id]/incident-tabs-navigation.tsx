"use client";

import { IoIosGitNetwork } from "react-icons/io";
import { Workflows } from "components/icons";
import { useParams, usePathname } from "next/navigation";
import { TabLinkNavigation, TabNavigationLink } from "@/shared/ui";
import { BellAlertIcon, BoltIcon } from "@heroicons/react/24/outline";
import { CiViewTimeline } from "react-icons/ci";
import { IncidentDto } from "@/entities/incidents/model";
import { useIncident, useIncidentAlerts } from "@/utils/hooks/useIncidents";
import { useTranslations } from "next-intl";

export function IncidentTabsNavigation() {
  const t = useTranslations("incidents.tabs");
  // Using type assertion because this component only renders on the /incidents/[id] routes
  const { id } = useParams<{ id: string }>() as { id: string };
  const pathname = usePathname();
  const { data: alerts } = useIncidentAlerts(id);

  const tabs = [
    { icon: BellAlertIcon, label: t("alerts"), path: "alerts" },
    { icon: BoltIcon, label: t("activity"), path: "activity", prefetch: true },
    { icon: CiViewTimeline, label: t("timeline"), path: "timeline" },
    {
      icon: IoIosGitNetwork,
      label: t("topology"),
      path: "topology",
    },
    { icon: Workflows, label: t("workflows"), path: "workflows" },
  ];

  return (
    <TabLinkNavigation className="sticky xl:-top-10 -top-4 bg-tremor-background-muted">
      {tabs.map((tab) => (
        <TabNavigationLink
          key={tab.path}
          icon={tab.icon}
          isActive={pathname?.endsWith(tab.path)}
          href={`/incidents/${id}/${tab.path}`}
          prefetch={!!tab.prefetch}
          count={tab.path === "alerts" ? alerts?.count : undefined}
        >
          {tab.label}
        </TabNavigationLink>
      ))}
    </TabLinkNavigation>
  );
}
