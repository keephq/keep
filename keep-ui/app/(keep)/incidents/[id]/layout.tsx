import { ReactNode } from "react";
import { IncidentTabsNavigation } from "./incident-tabs-navigation";
import { IncidentHeader } from "./incident-header";
import { getIncidentWithErrorHandling } from "./getIncidentWithErrorHandling";
import { IncidentHeaderSkeleton } from "./incident-header-skeleton";
import { IncidentChatClientPage } from "./chat/page.client";

export default async function Layout({
  children,
  params: serverParams,
}: {
  children: ReactNode;
  params: { id: string };
}) {
  const AIEnabled =
    !!process.env.OPEN_AI_API_KEY || !!process.env.OPENAI_API_KEY;
  try {
    const incident = await getIncidentWithErrorHandling(serverParams.id, false);
    return (
      <div className="flex flex-col gap-4">
        <IncidentHeader incident={incident} />
        <IncidentTabsNavigation incident={incident} />
        <div className="flex gap-4">
          <div className="flex-1 min-w-0">{children}</div>
          {AIEnabled && (
            <div className="w-[40%] shrink-0">
              <IncidentChatClientPage incident={incident} />
            </div>
          )}
        </div>
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
