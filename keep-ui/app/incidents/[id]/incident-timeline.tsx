import React from "react";
import { Chrono } from "react-chrono";
import { AuditEvent, useAlerts } from "utils/hooks/useAlerts";
import { IncidentDto } from "../model";
import { useIncidentAlerts } from "utils/hooks/useIncidents";
import { timeFormat } from "d3-time-format";
import {
  FaBell,
  FaCheck,
  FaBan,
  FaQuestion,
  FaPlay,
  FaRecycle,
} from "react-icons/fa";
import { FaGear } from "react-icons/fa6";
import { AlertDto } from "app/alerts/models";
import Image from "next/image";
import AlertSeverity from "app/alerts/alert-severity";

// Helper to format time for display
const formatTime = timeFormat("%b %d, %I:%M %p");

// Define the props interface for the IncidentTimeline component
interface Props {
  incident: IncidentDto;
}

// Helper function to get icon based on event action
const getEventIcon = (action: string): React.ReactNode => {
  if (action.includes("triggered"))
    return <FaBell title="Triggered" color="orange" />;
  if (action.includes("enriched"))
    return <FaGear title="Enriched" color="orange" />;
  if (action.includes("resolved"))
    return <FaCheck title="Resolved" color="orange" />;
  if (action.includes("suppressed"))
    return <FaBan title="Suppressed" color="orange" />;
  if (action.includes("deduplicated"))
    return <FaRecycle title="Deduplicated" color="orange" />;
  return <FaQuestion color="orange" />;
};

const DetailsComponent = ({
  _event,
  alert,
}: {
  _event: AuditEvent;
  alert: AlertDto | undefined;
}) => {
  return (
    <div className="flex flex-col">
      <p className="text-sm mt-1">
        {_event.description.replace("Alert", `Alert '${alert?.name}'`)}
      </p>
      {alert && (
        <div className="mt-2 text-sm">
          <p>
            <span className="font-semibold">Alert Name:</span> {alert.name}
          </p>
          <p>
            <span className="font-semibold">Status:</span> {alert.status}
          </p>
        </div>
      )}
    </div>
  );
};

const IncidentTimeline: React.FC<Props> = ({ incident }) => {
  const { data: alerts, isLoading: alertsLoading } = useIncidentAlerts(
    incident.id
  );
  const { useMultipleFingerprintsAlertAudit } = useAlerts();
  const { data: auditEvents, isLoading } = useMultipleFingerprintsAlertAudit(
    alerts?.items.map((m) => m.fingerprint)
  );

  if (isLoading || alertsLoading) {
    return <div>Loading...</div>;
  }

  const filterAuditEvents = (event: AuditEvent): boolean => {
    return event.action.includes("deduplicated") === false;
  };

  // Combine all audit events into a Chrono-compatible format
  const timelineItems = [
    {
      title: formatTime(new Date(incident.start_time!)),
      cardTitle: <FaPlay color="orange" />,
      cardSubtitle: `Incident created at ${formatTime(
        new Date(incident.start_time!)
      )}`,
    },
    ...(auditEvents
      ?.filter(filterAuditEvents)
      .sort(
        (a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      )
      .map((event) => {
        const alert = alerts?.items.find(
          (a) => a.fingerprint === event.fingerprint
        );
        return {
          title: formatTime(new Date(event.timestamp)),
          cardTitle: (
            <div className="flex w-full justify-between items-center">
              {getEventIcon(event.action)}
              <div className="flex items-center">
                <AlertSeverity severity={alert?.severity} />
                {alert?.source.map((source, index) => (
                  <Image
                    className={`inline-block ${index == 0 ? "" : "-ml-2"}`}
                    key={source}
                    alt={source}
                    height={24}
                    width={24}
                    title={source}
                    src={`/icons/${source}-icon.png`}
                  />
                ))}
              </div>
            </div>
          ),
          cardSubtitle: `Action: ${event.action}`,
          cardDetailedText: <DetailsComponent _event={event} alert={alert} />,
        };
      }) || []),
  ];

  return (
    <Chrono
      items={timelineItems}
      mode="VERTICAL" // Can be "VERTICAL" or "VERTICAL_ALTERNATING"
      cardHeight="30"
      theme={{
        primary: "orange",
        secondary: "rgb(255 247 237)",
        titleColor: "orange",
        titleColorActive: "orange",
      }}
      hideControls
      disableToolbar
      borderLessCards
      showAllCardsHorizontally
      useReadMore
    />
  );
};

export default IncidentTimeline;
