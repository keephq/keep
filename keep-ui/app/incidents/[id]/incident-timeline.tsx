"use client";

import React, { useMemo, useState } from "react";
import {
  format,
  parseISO,
  differenceInMinutes,
  differenceInHours,
  differenceInDays,
  addMinutes,
  addHours,
  addDays,
} from "date-fns";
import { AuditEvent, useAlerts } from "utils/hooks/useAlerts";
import { AlertDto } from "app/alerts/models";
import { useIncidentAlerts } from "utils/hooks/useIncidents";
import { IncidentDto } from "../model";
import Image from "next/image";
import AlertSeverity from "app/alerts/alert-severity";

const severityColors = {
  critical: "bg-red-400",
  high: "bg-orange-400",
  warning: "bg-blue-300",
  low: "bg-green-400",
  info: "bg-green-400",
  error: "bg-orange-400",
};

const dotColors = {
  "bg-red-400": "bg-red-500",
  "bg-orange-400": "bg-orange-500",
  "bg-blue-300": "bg-blue-400",
  "bg-green-400": "bg-green-500",
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
      <h2 className="font-semibold mb-2">{alert.name}</h2>
      <p className="mb-2 text-md">{alert.description}</p>
      <div className="flex w-80 justify-between text-sm items-center">
        <p className="text-gray-400">Date:</p>
        {format(parseISO(event.timestamp), "dd, MMM yyyy - HH:mm.ss 'UTC'")}
      </div>
      <div className="flex w-80 justify-between text-sm items-center">
        <p className="text-gray-400 text-sm">Severity:</p>
        <div className="flex items-center">
          <AlertSeverity severity={alert.severity} />
          <p>{alert.severity}</p>
        </div>
      </div>
      <div className="flex w-80 justify-between text-sm items-center">
        <p className="text-gray-400 text-sm">Source:</p>
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
      </div>
      <div className="flex w-80 justify-between text-sm items-center">
        <p className="text-gray-400 text-sm">Status:</p>
        {alert.status}
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
  const position =
    ((eventTime.getTime() - alertStart.getTime()) /
      (alertEnd.getTime() - alertStart.getTime())) *
    100;

  return (
    <div
      className={`absolute top-0 transform ${
        isSelected ? "h-full" : "h-3 top-1/2 -translate-y-1/2"
      } cursor-pointer transition-all duration-200`}
      style={{ left: `${position}%` }}
      onClick={() => onClick(event)}
    >
      <div
        className={`w-3 ${isSelected ? "h-full border-2 border-white" : "h-3"} ${
          dotColors[color as keyof typeof dotColors]
        } rounded-full`}
      ></div>
    </div>
  );
};

interface AlertBarProps {
  alert: AlertDto;
  auditEvents: AuditEvent[];
  startTime: Date;
  endTime: Date;
  timeScale: "minutes" | "hours" | "days";
  onEventClick: (event: AuditEvent | null) => void;
  selectedEventId: string | null;
}

const AlertBar: React.FC<AlertBarProps> = ({
  alert,
  auditEvents,
  startTime,
  endTime,
  timeScale,
  onEventClick,
  selectedEventId,
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
    <div className="relative h-12 mb-4">
      <div
        className={`absolute h-full rounded-full bg-white shadow-lg z-10 p-1`}
        style={{
          left: `${startPosition}%`,
          width: `${width}%`,
          minWidth: "20px", // Minimum width to ensure visibility
        }}
      >
        <div
          className={`h-full w-full rounded-full ${
            severityColors[alert.severity as keyof typeof severityColors] ||
            severityColors.info
          } relative`}
        >
          <div className="absolute inset-y-0 left-2 flex items-center text-white font-semibold truncate w-full pr-4">
            {alert.name}
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

export default function IncidentTimeline({
  incident,
}: {
  incident: IncidentDto;
}) {
  const { data: alerts, isLoading: alertsLoading } = useIncidentAlerts(
    incident.id
  );
  const { useMultipleFingerprintsAlertAudit } = useAlerts();
  const { data: auditEvents, isLoading: auditEventsLoading } =
    useMultipleFingerprintsAlertAudit(alerts?.items.map((m) => m.fingerprint));

  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);

  const timelineData = useMemo(() => {
    if (auditEvents) {
      const allTimestamps = auditEvents.map((event) =>
        parseISO(event.timestamp).getTime()
      );

      const startTime = new Date(Math.min(...allTimestamps));
      const endTime = new Date(Math.max(...allTimestamps));

      const paddedStartTime = new Date(startTime.getTime());
      const paddedEndTime = new Date(endTime.getTime());

      const daysDifference = differenceInDays(paddedEndTime, paddedStartTime);

      let timeScale: "minutes" | "hours" | "days";
      let intervals;
      let formatString;

      if (daysDifference > 3) {
        timeScale = "days";
        intervals = Array.from({ length: 9 }, (_, i) =>
          addDays(paddedStartTime, (i * daysDifference) / 8)
        );
        formatString = "MMM dd";
      } else if (daysDifference > 1) {
        timeScale = "hours";
        intervals = Array.from({ length: 9 }, (_, i) =>
          addHours(
            paddedStartTime,
            (i * differenceInHours(paddedEndTime, paddedStartTime)) / 8
          )
        );
        formatString = "HH:mm";
      } else {
        timeScale = "minutes";
        intervals = Array.from({ length: 9 }, (_, i) =>
          addMinutes(
            paddedStartTime,
            (i * differenceInMinutes(paddedEndTime, paddedStartTime)) / 8
          )
        );
        formatString = "HH:mm:ss";
      }

      return {
        startTime: paddedStartTime,
        endTime: paddedEndTime,
        intervals,
        formatString,
        timeScale,
      };
    }
    return {};
  }, [auditEvents]);

  if (auditEventsLoading || !auditEvents || alertsLoading) return <>No Data</>;

  const { startTime, endTime, intervals, formatString, timeScale } =
    timelineData;

  if (!intervals || !startTime || !endTime || !timeScale) return <>No Data</>;

  return (
    <div className="p-4">
      <div className="overflow-x-auto">
        <div style={{ minWidth: "100%", width: "max-content" }}>
          {/* Time labels */}
          <div className="flex justify-between mb-2">
            {intervals.map((time, index) => (
              <div key={index} className="text-xs px-2 text-gray-400">
                {format(time, formatString)}
              </div>
            ))}
          </div>

          {/* Alert bars */}
          <div className="space-y-4">
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
              .map((alert, index) => (
                <AlertBar
                  key={alert.id}
                  alert={alert}
                  auditEvents={auditEvents}
                  startTime={startTime}
                  endTime={endTime}
                  timeScale={timeScale}
                  onEventClick={setSelectedEvent}
                  selectedEventId={selectedEvent?.id || null}
                />
              ))}
          </div>
          <div className="h-5" />
          {/* Event details box */}
          {selectedEvent && (
            <AlertEventInfo
              event={selectedEvent}
              alert={
                alerts?.items.find(
                  (a) => a.fingerprint === selectedEvent.fingerprint
                )!
              }
            />
          )}
        </div>
      </div>
    </div>
  );
}
