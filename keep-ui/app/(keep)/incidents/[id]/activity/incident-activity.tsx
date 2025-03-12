"use client";

import { AlertDto } from "@/entities/alerts/model";
import { IncidentDto } from "@/entities/incidents/model";
import { useUsers } from "@/entities/users/model/useUsers";
import UserAvatar from "@/components/navbar/UserAvatar";
import "./incident-activity.css";
import {
  useIncidentAlerts,
  usePollIncidentComments,
} from "@/utils/hooks/useIncidents";
import { useAlerts } from "@/utils/hooks/useAlerts";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { IncidentActivityItem } from "./ui/IncidentActivityItem";
import { IncidentActivityComment } from "./ui/IncidentActivityComment";
import { useMemo } from "react";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { DynamicImageProviderIcon } from "@/components/ui";

// TODO: REFACTOR THIS TO SUPPORT ANY ACTIVITY TYPE, IT'S A MESS!

interface IncidentActivity {
  id: string;
  type: "comment" | "alert" | "newcomment" | "statuschange" | "assign";
  text?: string;
  timestamp: string;
  initiator?: string | AlertDto;
}

const ACTION_TYPES = [
  "alert was triggered",
  "alert acknowledged",
  "alert automatically resolved",
  "alert manually resolved",
  "alert status manually changed",
  "alert status changed by API",
  "alert automatically resolved by API",
  "A comment was added to the incident",
  "Incident status changed",
  "Incident assigned",
];

function Item({
  icon,
  children,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-4">
      <div className="relative py-6 w-12 flex items-center justify-center">
        {/* vertical line */}
        <div className="absolute mx-auto right-0 left-0 top-0 bottom-0 h-full bg-gray-200 w-px" />
        {/* wrapping icon to avoid vertical line visible behind transparent background */}
        <div className="relative z-[1] bg-tremor-background rounded-full border-2 border-tremor-background">
          {icon}
        </div>
      </div>
      <div className="py-6 flex-1">{children}</div>
    </div>
  );
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

  const auditActivities = useMemo(() => {
    if (!auditEvents.length && !incidentEvents.length) {
      return [];
    }
    return (
      auditEvents
        .concat(incidentEvents)
        .filter((auditEvent) => ACTION_TYPES.includes(auditEvent.action))
        .sort(
          (a, b) =>
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        )
        .map((auditEvent) => {
          const _type =
            auditEvent.action === "A comment was added to the incident" // @tb: I wish this was INCIDENT_COMMENT and not the text..
              ? "comment"
              : auditEvent.action === "Incident status changed"
              ? "statuschange"
              : auditEvent.action === "Incident assigned"
              ? "assign"
              : "alert";
          return {
            id: auditEvent.id,
            type: _type,
            initiator:
              _type === "comment" ||
              _type === "statuschange" ||
              _type === "assign"
                ? auditEvent.user_id
                : alerts?.items.find(
                    (a) => a.fingerprint === auditEvent.fingerprint
                  ),
            text:
              _type === "comment" ||
              _type === "statuschange" ||
              _type === "assign"
                ? auditEvent.description
                : "",
            timestamp: auditEvent.timestamp,
          } as IncidentActivity;
        }) || []
    );
  }, [auditEvents, incidentEvents, alerts]);

  const isLoading =
    incidentEventsLoading || auditEventsLoading || alertsLoading;

  const newCommentActivity: IncidentActivity = {
    id: "newcomment",
    type: "newcomment",
    timestamp: new Date().toISOString(),
    initiator: session?.user.email ?? "",
  };

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
      const source = (activity.initiator as AlertDto)?.source?.[0] || "keep";
      const imagePath = `/icons/${source}-icon.png`;
      return (
        <DynamicImageProviderIcon
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

  return (
    <div className="flex flex-col max-w-3xl mx-auto">
      <Item icon={renderIcon(newCommentActivity)}>
        <IncidentActivityComment
          incident={incident}
          mutator={mutateIncidentActivity}
        />
      </Item>
      {isLoading
        ? Array.from({ length: 10 }).map((_, i) => (
            <Item
              key={i}
              icon={<Skeleton className="!w-6 !h-6 !rounded-full" />}
            >
              <Skeleton className="w-full h-6" />
            </Item>
          ))
        : auditActivities.map((activity) => (
            <Item key={activity.id} icon={renderIcon(activity)}>
              <IncidentActivityItem key={activity.id} activity={activity} />
            </Item>
          ))}
    </div>
  );
}
