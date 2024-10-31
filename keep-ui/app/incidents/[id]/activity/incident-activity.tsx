"use client";

import { AlertDto } from "@/app/alerts/models";
import { IncidentDto } from "../../models";
import { useUsers } from "@/utils/hooks/useUsers";
import Image from "next/image";
import UserAvatar from "@/components/navbar/UserAvatar";
import "./incident-activity.css";
import {
  useIncidentAlerts,
  usePollIncidentComments,
} from "@/utils/hooks/useIncidents";
import { useAlerts } from "@/utils/hooks/useAlerts";
import Loading from "@/app/loading";
import { useSession } from "next-auth/react";
import { IncidentActivityItem } from "./ui/IncidentActivityItem";
import { IncidentActivityComment } from "./ui/IncidentActivityComment";
import dynamic from "next/dynamic";

// react-chrono is not compatible with server-side rendering, so we need to import it dynamically
const Chrono = dynamic(
  () => import("react-chrono").then((mod) => mod.Chrono),
  { ssr: false } // Disable SSR for this component
);

interface IncidentActivity {
  id: string;
  type: "comment" | "alert" | "newcomment";
  text?: string;
  timestamp: string;
  initiator?: string | AlertDto;
}

// FIX: if the activity loaded as SSR, there's no activities displayed, only comment field is shown
export function IncidentActivity({ incident }: { incident: IncidentDto }) {
  const { data: session } = useSession();
  const { useMultipleFingerprintsAlertAudit, useAlertAudit } = useAlerts();
  const { data: alerts, isLoading: alertsLoading } = useIncidentAlerts(
    incident.id
  );
  const { data: auditEvents, isLoading: auditEventsLoading } =
    useMultipleFingerprintsAlertAudit(alerts?.items.map((m) => m.fingerprint));
  const {
    data: incidentEvents,
    isLoading: incidentEventsLoading,
    mutate: mutateIncidentActivity,
  } = useAlertAudit(incident.id);

  const { data: users, isLoading: usersLoading } = useUsers();
  usePollIncidentComments(incident.id);

  if (
    usersLoading ||
    incidentEventsLoading ||
    auditEventsLoading ||
    alertsLoading
  ) {
    return <Loading />;
  }

  const newCommentActivity = {
    id: "newcomment",
    type: "newcomment",
    timestamp: new Date().toISOString(),
    initiator: session?.user.email,
  };

  const auditActivities =
    auditEvents
      ?.concat(incidentEvents || [])
      .sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      )
      .map((auditEvent) => {
        const _type =
          auditEvent.action === "A comment was added to the incident" // @tb: I wish this was INCIDENT_COMMENT and not the text..
            ? "comment"
            : "alert";
        return {
          id: auditEvent.id,
          type: _type,
          initiator:
            _type === "comment"
              ? auditEvent.user_id
              : alerts?.items.find(
                  (a) => a.fingerprint === auditEvent.fingerprint
                ),
          text: _type === "comment" ? auditEvent.description : "",
          timestamp: auditEvent.timestamp,
        } as IncidentActivity;
      }) || [];

  const activities = [newCommentActivity, ...auditActivities];

  const chronoContent = activities?.map((activity, index) =>
    activity.type === "newcomment" ? (
      <IncidentActivityComment
        mutator={mutateIncidentActivity}
        incident={incident}
        key={activity.id}
      />
    ) : (
      <IncidentActivityItem key={activity.id} activity={activity} />
    )
  );
  const chronoIcons = activities?.map((activity, index) => {
    if (activity.type === "comment" || activity.type === "newcomment") {
      const user = users?.find((user) => user.email === activity.initiator);
      return (
        <UserAvatar
          key={`icon-${activity.id}`}
          image={user?.picture}
          name={
            user?.name ?? user?.email ?? (activity.initiator as string) ?? ""
          }
        />
      );
    } else {
      const source = (activity.initiator as AlertDto)?.source?.[0];
      const imagePath = `/icons/${source}-icon.png`;
      return (
        <Image
          key={`icon-${activity.id}`}
          alt={source}
          height={24}
          width={24}
          title={source}
          src={imagePath}
        />
      );
    }
  });

  return (
    <Chrono
      items={activities?.map((activity) => ({
        id: activity.id,
        title: activity.timestamp,
      }))}
      hideControls
      disableToolbar
      borderLessCards={true}
      slideShow={false}
      mode="VERTICAL"
      cardWidth={600}
      cardHeight={100}
      allowDynamicUpdate={true}
      disableAutoScrollOnClick={true}
    >
      {chronoContent}
      <div className="chrono-icons">{chronoIcons}</div>
    </Chrono>
  );
}
