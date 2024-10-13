import { AlertDto } from "@/app/alerts/models";
import { IncidentDto } from "../models";
import { Chrono } from "react-chrono";
import { useUsers } from "@/utils/hooks/useUsers";
import Image from "next/image";
import UserAvatar from "@/components/navbar/UserAvatar";
import "./incident-activity.css";
import AlertSeverity from "@/app/alerts/alert-severity";
import TimeAgo from "react-timeago";
import { Button, TextInput } from "@tremor/react";
import { useIncidentAlerts } from "@/utils/hooks/useIncidents";
import { AuditEvent, useAlerts } from "@/utils/hooks/useAlerts";
import Loading from "@/app/loading";
import { useState } from "react";
import { getApiURL } from "@/utils/apiUrl";
import { useSession } from "next-auth/react";
import { KeyedMutator } from "swr";
import { toast } from "react-toastify";

interface IncidentActivity {
  id: string;
  type: "comment" | "alert" | "newcomment";
  text?: string;
  timestamp: string;
  initiator?: string | AlertDto;
}

export function IncidentActivityChronoItem({ activity }: { activity: any }) {
  const title =
    typeof activity.initiator === "string"
      ? activity.initiator
      : activity.initiator?.name;
  const subTitle =
    typeof activity.initiator === "string"
      ? " Added a comment. "
      : (activity.initiator?.status === "firing" ? " triggered" : " resolved") +
        ". ";
  return (
    <div className="relative h-full w-full flex items-center">
      {activity.type === "alert" && (
        <AlertSeverity
          severity={(activity.initiator as AlertDto).severity}
          marginLeft={false}
        />
      )}
      <span className="font-semibold mr-2.5">{title}</span>
      <span className="text-gray-300">
        {subTitle} <TimeAgo date={activity.timestamp + "Z"} />
      </span>
      {activity.text && (
        <div className="absolute top-14 font-light text-gray-400">
          {activity.text}
        </div>
      )}
    </div>
  );
}

export function IncidentActivityChronoItemComment({
  incident,
  mutator,
}: {
  incident: IncidentDto;
  mutator: KeyedMutator<AuditEvent[]>;
}) {
  const [comment, setComment] = useState("");
  const apiUrl = getApiURL();
  const { data: session } = useSession();

  const onSubmit = async () => {
    const response = await fetch(`${apiUrl}/incidents/${incident.id}/comment`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        status: incident.status,
        comment: comment,
      }),
    });
    if (response.ok) {
      toast.success("Comment added!", { position: "top-right" });
      setComment("");
      mutator();
    } else {
      toast.error("Failed to add comment", { position: "top-right" });
    }
  };

  return (
    <div className="flex h-full w-full relative items-center">
      <TextInput value={comment} onValueChange={setComment} />
      <Button
        color="orange"
        variant="secondary"
        className="ml-2.5"
        disabled={!comment}
        onClick={onSubmit}
      >
        Submit
      </Button>
    </div>
  );
}

export default function IncidentActivity({
  incident,
}: {
  incident: IncidentDto;
}) {
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

  if (
    usersLoading ||
    incidentEventsLoading ||
    auditEventsLoading ||
    alertsLoading
  )
    return <Loading />;

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
          text: auditEvent.description,
          timestamp: auditEvent.timestamp,
        } as IncidentActivity;
      }) || [];

  const activities = [newCommentActivity, ...auditActivities];

  const chronoContent = activities?.map((activity, index) =>
    activity.type === "newcomment" ? (
      <IncidentActivityChronoItemComment
        mutator={mutateIncidentActivity}
        incident={incident}
        key={index}
      />
    ) : (
      <IncidentActivityChronoItem key={index} activity={activity} />
    )
  );
  const chronoIcons = activities?.map((activity, index) => {
    if (activity.type === "comment" || activity.type === "newcomment") {
      const user = users?.find((user) => user.email === activity.initiator);
      return (
        <UserAvatar
          key={`icon-${index}`}
          image={user?.picture}
          name={user?.name ?? user?.email ?? (activity.initiator as string)}
        />
      );
    } else {
      const source = (activity.initiator as AlertDto).source[0];
      const imagePath = `/icons/${source}-icon.png`;
      return (
        <Image
          key={`icon-${index}`}
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
        title: activity.timestamp,
      }))}
      hideControls
      disableToolbar
      borderLessCards={true}
      slideShow={false}
      mode="VERTICAL"
      cardWidth={600}
      cardHeight={100}
    >
      {chronoContent}
      <div className="chrono-icons">{chronoIcons}</div>
    </Chrono>
  );
}
