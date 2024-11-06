import { ReactNode } from "react";
import { IncidentTabsNavigation } from "./incident-tabs-navigation";
import { IncidentHeader } from "./incident-header";
import { getIncidentWithErrorHandling } from "./getIncidentWithErrorHandling";
import { IncidentHeaderSkeleton } from "./incident-header-skeleton";

export default async function Layout({
  children,
  params: serverParams,
}: {
  children: ReactNode;
  params: { id: string };
}) {
  // TODO: check if this request duplicated
  try {
    const incident = await getIncidentWithErrorHandling(serverParams.id, false);
    return (
      <div className="flex flex-col gap-4">
        <IncidentHeader incident={incident} />
        <IncidentTabsNavigation incident={incident} />
        {children}
      </div>
    );
  } catch (error) {
    return (
      <div className="flex flex-col gap-4">
        <IncidentHeaderSkeleton />
        {children}
      </div>
    );
  }
}
