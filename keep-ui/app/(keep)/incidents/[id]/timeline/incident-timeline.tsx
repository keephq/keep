"use client";

import Loading from "@/app/(keep)/loading";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import type { IncidentDto } from "@/entities/incidents/model";
import { AuditEvent, useAlerts } from "@/utils/hooks/useAlerts";
import { useIncidentAlerts } from "@/utils/hooks/useIncidents";
import { Card } from "@tremor/react";
import AlertSeverity from "@/app/(keep)/alerts/alert-severity";
import { AlertDto } from "@/app/(keep)/alerts/models";
import { format, parseISO } from "date-fns";
import Image from "next/image";
import { useRouter } from "next/navigation";
import React, { useEffect, useMemo, useState } from "react";

const severityColors = {
  critical: "bg-red-300",
  high: "bg-orange-300",
  warning: "bg-blue-200",
  low: "bg-green-300",
  info: "bg-green-300",
  error: "bg-orange-300",
};

const dotColors = {
  "bg-red-300": "bg-red-500",
  "bg-orange-300": "bg-orange-500",
  "bg-blue-200": "bg-blue-400",
  "bg-green-300": "bg-green-500",
};

const severityTextColors = {
  critical: "text-red-500",
  high: "text-orange-500",
  warning: "text-yellow-500",
  low: "text-green-500",
  info: "text-emerald-500",
  error: "text-orange-500",
};

interface EventDotProps {
  event: AuditEvent;
  alertStart: Date;
  alertEnd: Date;
  color: string;
  onClick: (event: AuditEvent) => void;
  isSelected: boolean;
}

const AlertEventInfo: React.FC<{ event: AuditEvent; alert: AlertDto }> = ({
  event,
  alert,
}) => {
  return (
    <div className="mt-4 p-4 bg-gray-100">
      <h2 className="font-semibold mb-2">
        {alert.name} ({alert.fingerprint})
      </h2>
      <p className="mb-2 text-md">{alert.description}</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <p className="text-gray-400">Date:</p>
        <p>
          {format(parseISO(event.timestamp), "dd, MMM yyyy - HH:mm:ss 'UTC'")}
        </p>

        <p className="text-gray-400">Action:</p>
        <p>{event.action}</p>

        <p className="text-gray-400">Description:</p>
        <p>{event.description}</p>

        <p className="text-gray-400">Severity:</p>
        <div className="flex items-center">
          <AlertSeverity severity={alert.severity} />
          <p className="ml-2">{alert.severity}</p>
        </div>

        <p className="text-gray-400">Source:</p>
        <div className="flex items-center">
          {alert.source.map((source, index) => (
            <Image
              className={`inline-block mr-2 ${index == 0 ? "" : "-ml-2"}`}
              key={source}
              alt={source}
              height={24}
              width={24}
              title={source}
              src={`/icons/${source}-icon.png`}
            />
          ))}
          <p>{alert.source.join(",")}</p>
        </div>

        <p className="text-gray-400">Status:</p>
        <p>{alert.status}</p>
      </div>
    </div>
  );
};

const EventDot: React.FC<EventDotProps> = ({
  event,
  alertStart,
  alertEnd,
  color,
  onClick,
  isSelected,
}) => {
  const eventTime = parseISO(event.timestamp);
  let position =
    ((eventTime.getTime() - alertStart.getTime()) /
      (alertEnd.getTime() - alertStart.getTime())) *
    100;
  if (position == 0) position = 5;
  if (position == 100) position = 90;

  return (
    <div
      className={`absolute top-0 transform ${
        isSelected ? "h-full" : "h-3 top-1/2 -translate-y-1/2"
      } cursor-pointer transition-all duration-200`}
      style={{ left: `${position}%` }}
      onClick={() => onClick(event)}
    >
      <div
        className={`w-3 ${
          isSelected ? "h-full border-2 border-white" : "h-3 animate-pulse"
        } ${dotColors[color as keyof typeof dotColors]} rounded-full`}
      ></div>
    </div>
  );
};

interface AlertBarProps {
  alert: AlertDto;
  auditEvents: AuditEvent[];
  startTime: Date;
  endTime: Date;
  timeScale: "seconds" | "minutes" | "hours" | "days";
  onEventClick: (event: AuditEvent | null) => void;
  selectedEventId: string | null;
  isFirstRow: boolean;
  isLastRow: boolean;
}

const AlertBar: React.FC<AlertBarProps> = ({
  alert,
  auditEvents,
  startTime,
  endTime,
  timeScale,
  onEventClick,
  selectedEventId,
  isFirstRow,
  isLastRow,
}) => {
  const alertEvents = auditEvents.filter(
    (event) => event.fingerprint === alert.fingerprint
  );
  const alertStart = new Date(
    Math.min(...alertEvents.map((e) => parseISO(e.timestamp).getTime()))
  );
  const alertEnd = new Date(
    Math.max(...alertEvents.map((e) => parseISO(e.timestamp).getTime()))
  );

  const startPosition =
    ((alertStart.getTime() - startTime.getTime()) /
      (endTime.getTime() - startTime.getTime())) *
    100;
  let width =
    ((alertEnd.getTime() - alertStart.getTime()) /
      (endTime.getTime() - startTime.getTime())) *
    100;

  // Ensure the width is at least 0.5% to make it visible
  width = Math.max(width, 0.5);

  const handleEventClick = (event: AuditEvent) => {
    onEventClick(selectedEventId === event.id ? null : event);
  };

  return (
    <div className="relative h-14 flex items-center">
      <div className="absolute inset-0 grid grid-cols-24">
        {Array.from({ length: 24 }).map((_, index) => (
          <div
            key={index}
            className={`border-gray-100 border-b ${
              isFirstRow ? "border-t-0" : "border-t"
            }
            ${index === 0 ? "border-l-0" : "border-l"} ${
              index === 23 ? "border-r-0" : "border-r"
            }`}
          />
        ))}
      </div>
      <div
        className={`absolute h-12 rounded-full bg-white shadow-lg z-10 p-1`}
        style={{
          left: `${startPosition}%`,
          width: `${width}%`,
          minWidth: "200px", // Minimum width to ensure visibility
        }}
      >
        <div
          className={`h-full w-full rounded-full ${
            severityColors[alert.severity as keyof typeof severityColors] ||
            severityColors.info
          } relative overflow-hidden`}
        >
          <div className="absolute inset-y-0 left-2 flex items-center font-semibold truncate w-full pr-4">
            <AlertSeverity severity={alert.severity} />
            <span
              className={`ml-2 ${
                severityTextColors[
                  alert.severity as keyof typeof severityTextColors
                ] || severityTextColors.info
              }`}
            >
              {alert.name}
            </span>
          </div>
          {alertEvents.map((event, index) => (
            <EventDot
              key={event.id}
              event={event}
              alertStart={alertStart}
              alertEnd={alertEnd}
              color={
                severityColors[alert.severity as keyof typeof severityColors] ||
                severityColors.info
              }
              onClick={handleEventClick}
              isSelected={selectedEventId === event.id}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

const IncidentTimelineNoAlerts: React.FC = () => {
  const router = useRouter();
  return (
    <div className="h-80">
      <EmptyStateCard
        title="Timeline not available"
        description="No alerts found for this incident. Go to the alerts feed and assign alerts to view the timeline."
        buttonText="Assign alerts to this incident"
        onClick={() => router.push("/alerts/feed")}
      />
    </div>
  );
};

export default function IncidentTimeline({
  incident,
}: {
  incident: IncidentDto;
}) {
  const {
    data: alerts,
    isLoading: _alertsLoading,
    error: alertsError,
  } = useIncidentAlerts(incident.id);
  const { useMultipleFingerprintsAlertAudit } = useAlerts();
  const {
    data: auditEvents,
    isLoading: _auditEventsLoading,
    error: auditEventsError,
    mutate,
  } = useMultipleFingerprintsAlertAudit(
    alerts?.items.map((m) => m.fingerprint)
  );

  // TODO: Load data on server side
  // Loading state is true if the data is not loaded and there is no error for smoother loading state on initial load
  const alertsLoading = _alertsLoading || (!alerts && !alertsError);
  const auditEventsLoading =
    _auditEventsLoading || (!auditEvents && !auditEventsError);

  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);

  useEffect(() => {
    mutate();
  }, [alerts, mutate]);

  const timelineData = useMemo(() => {
    if (auditEvents && alerts) {
      const allTimestamps = auditEvents.map((event) =>
        parseISO(event.timestamp).getTime()
      );

      const startTime = new Date(Math.min(...allTimestamps));
      const endTime = new Date(Math.max(...allTimestamps));

      // Add padding to end time only
      const paddedEndTime = new Date(endTime.getTime() + 1000 * 60); // 1 minute after

      const totalDuration = paddedEndTime.getTime() - startTime.getTime();
      const pixelsPerMillisecond = 5000 / totalDuration; // Assuming 5000px minimum width

      let timeScale: "seconds" | "minutes" | "hours" | "days";
      let intervalDuration: number;
      let formatString: string;

      if (totalDuration > 3 * 24 * 60 * 60 * 1000) {
        timeScale = "days";
        intervalDuration = 24 * 60 * 60 * 1000;
        formatString = "MMM dd";
      } else if (totalDuration > 24 * 60 * 60 * 1000) {
        timeScale = "hours";
        intervalDuration = 60 * 60 * 1000;
        formatString = "HH:mm";
      } else if (totalDuration > 60 * 60 * 1000) {
        timeScale = "minutes";
        intervalDuration = 5 * 60 * 1000; // 5-minute intervals
        formatString = "HH:mm";
      } else {
        timeScale = "seconds";
        intervalDuration = 10 * 1000; // 10-second intervals
        formatString = "HH:mm:ss";
      }

      const intervals: Date[] = [];
      let currentTime = startTime;
      while (currentTime <= paddedEndTime) {
        intervals.push(new Date(currentTime));
        currentTime = new Date(currentTime.getTime() + intervalDuration);
      }

      return {
        startTime,
        endTime: paddedEndTime,
        intervals,
        formatString,
        timeScale,
        pixelsPerMillisecond,
      };
    }
    return {};
  }, [auditEvents, alerts]);

  if (auditEventsLoading || alertsLoading) {
    return (
      <Card>
        <Loading />
      </Card>
    );
  }

  if (!auditEvents || !alerts) {
    return <IncidentTimelineNoAlerts />;
  }

  const {
    startTime,
    endTime,
    intervals,
    formatString,
    timeScale,
    pixelsPerMillisecond,
  } = timelineData;

  if (
    !intervals ||
    !startTime ||
    !endTime ||
    !timeScale ||
    !pixelsPerMillisecond
  )
    return <>No Data</>;

  const totalWidth = Math.max(
    5000,
    (endTime.getTime() - startTime.getTime()) * pixelsPerMillisecond
  );

  return (
    <Card className="py-2 px-0">
      <div className="overflow-x-auto">
        <div style={{ width: `${totalWidth}px`, minWidth: "100%" }}>
          {/* Time labels */}
          <div
            className="flex mb-2 relative"
            style={{ height: "20px", paddingLeft: "40px" }}
          >
            {intervals.map((time, index) => (
              <div
                key={index}
                className="text-xs px-2 text-gray-400 absolute whitespace-nowrap"
                style={{
                  left: `${
                    (time.getTime() - startTime.getTime()) *
                    pixelsPerMillisecond
                  }px`,
                  transform: "translateX(-50%)",
                }}
              >
                {format(time, formatString)}
              </div>
            ))}
          </div>

          {/* Alert bars */}
          <div className="space-y-0">
            {alerts?.items
              .sort((a, b) => {
                const aStart = Math.min(
                  ...auditEvents
                    .filter((e) => e.fingerprint === a.fingerprint)
                    .map((e) => parseISO(e.timestamp).getTime())
                );
                const bStart = Math.min(
                  ...auditEvents
                    .filter((e) => e.fingerprint === b.fingerprint)
                    .map((e) => parseISO(e.timestamp).getTime())
                );
                return aStart - bStart;
              })
              .map((alert, index, array) => (
                <AlertBar
                  key={alert.id}
                  alert={alert}
                  auditEvents={auditEvents}
                  startTime={startTime}
                  endTime={endTime}
                  timeScale={timeScale}
                  onEventClick={setSelectedEvent}
                  selectedEventId={selectedEvent?.id || null}
                  isFirstRow={index === 0}
                  isLastRow={index === array.length - 1}
                />
              ))}
          </div>
        </div>
      </div>
      <div className="h-3" />
      {/* Event details box */}
      {selectedEvent && (
        <div className="overflow-x-hidden">
          <AlertEventInfo
            event={selectedEvent}
            alert={
              alerts?.items.find(
                (a) => a.fingerprint === selectedEvent.fingerprint
              )!
            }
          />
        </div>
      )}
    </Card>
  );
}
