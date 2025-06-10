"use client";

import React, { useState } from "react";
import type { IncidentDto } from "@/entities/incidents/model";
import { useIncidentTimeline } from "@/utils/hooks/useIncidents";
import { Button, Card } from "@tremor/react";
import { AlertSeverity } from "@/entities/alerts/ui";
import { AlertDto, AuditEvent } from "@/entities/alerts/model";
import {
  format,
  parseISO,
} from "date-fns";
import { useRouter } from "next/navigation";
import { DynamicImageProviderIcon } from "@/components/ui";
import { CiViewTimeline } from "react-icons/ci";
import { KeepLoader, EmptyStateCard } from "@/shared/ui";
import { FormattedContent } from "@/shared/ui/FormattedContent/FormattedContent";
import { IncidentTimelineAlertDto } from "@/entities/incidents/model/models";

const cellWidth = 50;

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
    <div className="h-full p-4 bg-gray-100 border-l">
      <h2 className="font-semibold mb-2">
        {alert.name} (<small>Fingerprint: {alert.fingerprint}</small>)
      </h2>
      <p className="mb-2 text-md">
        <FormattedContent
          content={alert.description}
          format={alert.description_format}
        />
      </p>
      <div className="grid grid-cols-4 gap-x-4 gap-y-2 text-sm">
        <p className="text-gray-400">Date:</p>
        <p className="col-span-3">
          {format(parseISO(event.timestamp), "dd, MMM yyyy - HH:mm:ss 'UTC'")}
        </p>

        <p className="text-gray-400">Action:</p>
        <p className="col-span-3">{event.action}</p>

        <p className="text-gray-400">Description:</p>
        <p className="col-span-3">{event.description}</p>

        <p className="text-gray-400">Severity:</p>
        <div className="flex items-center col-span-3">
          <AlertSeverity severity={alert.severity} />
          <p className="ml-2">{alert.severity}</p>
        </div>

        <p className="text-gray-400">Source:</p>
        <div className="flex items-center col-span-3">
          {alert.source.map((source, index) => (
            <DynamicImageProviderIcon
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
        <p className="col-span-3">{alert.status}</p>
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
  timelineAlert: IncidentTimelineAlertDto;
  timelineStart: Date;
  timelineEnd: Date;
  timeScale: "seconds" | "minutes" | "hours" | "days";
  onEventClick: (event: AuditEvent | null) => void;
  selectedEventId: string | null;
  isFirstRow: boolean;
  isLastRow: boolean;
}

const AlertBar: React.FC<AlertBarProps> = ({
  timelineAlert,
  timelineStart,
  timelineEnd,
  timeScale,
  onEventClick,
  selectedEventId,
  isFirstRow,
  isLastRow,
}) => {

  const alert = timelineAlert.alert;
  const alertEvents = timelineAlert.events;
  const alertStart = new Date(timelineAlert.start);
  const alertEnd = new Date(timelineAlert.end);

  const startPosition =
    ((alertStart.getTime() - timelineStart.getTime()) /
      (timelineEnd.getTime() - timelineStart.getTime())) *
    24;

  let width = timelineAlert.duration[timeScale] * 24;

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
          left: `${startPosition}px`,
          width: `${width}px`,
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
        icon={CiViewTimeline}
        title="No Timeline Yet"
        description="No alerts found for this incident. Go to the alerts feed and assign alerts to view the timeline."
      >
        <Button
          color="orange"
          variant="primary"
          size="md"
          onClick={() => router.push("/alerts/feed")}
        >
          Assign Alerts
        </Button>
      </EmptyStateCard>
    </div>
  );
};

export default function IncidentTimeline({
  incident,
}: {
  incident: IncidentDto;
}) {
  const {
    data: timelineServerData,
    isLoading: _timelineLoading,
    error: timelineError,
  } = useIncidentTimeline(incident.id);

  interface SelectedEvent {
    alert: AlertDto | null;
    event: AuditEvent | null;
  }

  const [selectedEvent, setSelectedEvent] = useState<SelectedEvent | null>(null);

  if (_timelineLoading) {
    return (
      <Card>
        <KeepLoader />
      </Card>
    );
  }

  if (!timelineServerData || timelineServerData?.alerts?.length === 0) {
    return <IncidentTimelineNoAlerts />;
  }

  const startTime = new Date(timelineServerData.start);
  const endTime = new Date(timelineServerData.end);

  let timeScale: "seconds" | "minutes" | "hours" | "days";
  let formatString: string;

  // Determine scale and format based on total duration
  const durationInDays = timelineServerData.duration.days;
  const durationInHours = timelineServerData.duration.hours;
  const durationInMinutes = timelineServerData.duration.minutes;
  console.log(
    `Duration in days: ${durationInDays}, duration in hours: ${durationInHours}, duration in minutes: ${durationInMinutes}`
  );

  if (durationInDays >= 1) {
    timeScale = "days";
    formatString = "MMM dd";
  } else if (12 < durationInHours && durationInHours < 23) {
    timeScale = "hours";
    formatString = "MMM dd HH:mm";
  } else if (durationInMinutes > 60) {
    timeScale = "minutes";
    formatString = "HH:mm";
  } else {
    timeScale = "seconds";
    formatString = "HH:mm:ss";
  }


  // let totalWidth = timelineServerData.duration[timeScale] * 24;

  return (
    <div className="flex flex-col">
      <div className="flex-grow transition-all duration-300">
        <Card
          className="py-2 px-0 overflow-y-auto"
          style={{
            maxHeight: `calc(100vh - ${selectedEvent ? "630px" : "430px"})`,
          }}
        >
          <div className="flex">
            <div
              className="flex flex-col flex-grow transition-all duration-300 w-full"
            >
              <div className="flex flex-grow overflow-x-auto">
                <div style={{  minWidth: "100%" }}>
                  {/* Alert bars */}
                  <div className="space-y-0">
                    {timelineServerData.alerts.map((timelineAlert, index, array) => (
                        <AlertBar
                          key={timelineAlert.alert.id}
                          timelineAlert={timelineAlert}
                          timelineStart={startTime}
                          timelineEnd={endTime}
                          timeScale={timeScale}
                          onEventClick={(event) => setSelectedEvent({alert: timelineAlert.alert, event: event})}
                          selectedEventId={selectedEvent?.event?.id || null}
                          isFirstRow={index === 0}
                          isLastRow={index === array.length - 1}
                        />
                      ))}
                  </div>
                </div>
              </div>

              {/* Time labels - Now sticky at bottom */}
              <div className="sticky -bottom-2 z-20 bg-white border-t">
                <div
                  className="relative overflow-hidden"
                  style={{
                    height: "50px",
                    paddingLeft: "40px",
                    paddingRight: "40px",
                  }}
                >
                  {/*{intervals.map((time, index) => (*/}
                  {/*  <div*/}
                  {/*    key={index}*/}
                  {/*    className="absolute flex flex-col items-center text-xs text-gray-400 h-[50px]"*/}
                  {/*    style={{*/}
                  {/*      left: `${*/}
                  {/*        ((time.getTime() - startTime.getTime()) **/}
                  {/*          pixelsPerMillisecond || 30) -*/}
                  {/*        (index === intervals.length - 1 ? 50 : 0)*/}
                  {/*      }px`,*/}
                  {/*      transform: "translateX(-50%)",*/}
                  {/*    }}*/}
                  {/*  >*/}
                  {/*    <div className="h-4 border-l border-gray-300 mb-1"></div>*/}
                  {/*    <div>{format(time, "MMM dd")}</div>*/}
                  {/*    <div className="text-gray-500">*/}
                  {/*      {format(time, "HH:mm")}*/}
                  {/*    </div>*/}
                  {/*  </div>*/}
                  {/*))}*/}
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>
      <div className="">
        {/* Event details box */}
        {selectedEvent && selectedEvent.event && selectedEvent.alert && (
          <div
            className="overflow-y-auto"
            style={{ height: "calc(100% - 50px)", maxHeight: "250px" }}
          >
            <AlertEventInfo
              event={selectedEvent.event}
              alert={selectedEvent.alert}
            />
          </div>
        )}
      </div>
    </div>
  );
}
