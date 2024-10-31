import { ReactNode } from "react";
import { IncidentTabsNavigation } from "./incident-tabs-navigation";
import { IncidentHeader } from "./incident-header";
import { getApiURL } from "@/utils/apiUrl";
import { getIncident } from "@/entities/incidents/api/incidents";
import { getServerSession } from "next-auth";
import { authOptions } from "@/pages/api/auth/[...nextauth]";

export default async function Layout({
  children,
  params: serverParams,
}: {
  children: ReactNode;
  params: { id: string };
}) {
  // TODO: check if this request duplicated
  const session = await getServerSession(authOptions);
  const apiUrl = getApiURL();
  const incident = await getIncident(apiUrl, session, serverParams.id);

  return (
    <div className="flex flex-col gap-4">
      <IncidentHeader incident={incident} />
      <IncidentTabsNavigation />
      {/* TODO: ensure navigation happens right away */}
      {children}
    </div>
  );
}
