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
import { useMemo } from "react";

interface IncidentActivity {
  id: string;
  type: "comment" | "alert" | "newcomment";
  text?: string;
  timestamp: string;
  initiator?: string | AlertDto;
}

export function IncidentActivity({ incident }: { incident: IncidentDto }) {
  const { data: session } = useSession();
  const { useMultipleFingerprintsAlertAudit, useAlertAudit } = useAlerts();
  const {
    data: alerts,
    isLoading: _alertsLoading,
    error: alertsError,
  } = useIncidentAlerts(incident.id);
  const {
    data: auditEvents = [],
    isLoading: _auditEventsLoading,
    error: auditEventsError,
  } = useMultipleFingerprintsAlertAudit(
    alerts?.items.map((m) => m.fingerprint)
  );
  const {
    data: incidentEvents = [],
    isLoading: _incidentEventsLoading,
    error: incidentEventsError,
    mutate: mutateIncidentActivity,
  } = useAlertAudit(incident.id);

  const {
    data: users,
    isLoading: _usersLoading,
    error: usersError,
  } = useUsers();
  usePollIncidentComments(incident.id);

  // TODO: Load data on server side
  // Loading state is true if the data is not loaded and there is no error for smoother loading state on initial load
  const alertsLoading = _alertsLoading || (!alerts && !alertsError);
  const auditEventsLoading =
    _auditEventsLoading || (!auditEvents && !auditEventsError);
  const incidentEventsLoading =
    _incidentEventsLoading || (!incidentEvents && !incidentEventsError);
  const usersLoading = _usersLoading || (!users && !usersError);

  const auditActivities = useMemo(() => {
    if (!auditEvents.length && !incidentEvents.length) {
      return [];
    }
    return (
      auditEvents
        .concat(incidentEvents)
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
        }) || []
    );
  }, [auditEvents, incidentEvents, alerts]);

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

  const activities = [newCommentActivity, ...auditActivities];

  const renderActivity = (activity: IncidentActivity) =>
    activity.type === "newcomment" ? (
      <IncidentActivityComment
        mutator={mutateIncidentActivity}
        incident={incident}
        key={activity.id}
      />
    ) : (
      <IncidentActivityItem key={activity.id} activity={activity} />
    );

  const renderIcon = (activity: IncidentActivity) => {
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
  };

  const renderItem = (item: any) => {
    return (
      <div className="flex gap-4">
        <div className="relative py-6 w-12 flex items-center justify-center">
          {/* vertical line */}
          <div className="absolute mx-auto right-0 left-0 top-0 bottom-0 h-full bg-gray-200 w-px" />
          {/* wrapping icon to avoid vertical line visible behind transparent background */}
          <div className="relative z-[1] bg-tremor-background rounded-full border border-2 border-tremor-background">
            {renderIcon(item)}
          </div>
        </div>
        <div className="py-6 flex-1">{renderActivity(item)}</div>
      </div>
    );
  };

  return (
    <div className="flex flex-col">
      {activities?.map((activity) => renderItem(activity))}
    </div>
  );
}
