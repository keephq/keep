import React from "react";
import { Subtitle, Button } from "@tremor/react";
import { Chrono } from "react-chrono";
import Image from "next/image";
import { ArrowPathIcon } from "@heroicons/react/24/outline";
import { AlertDto } from "./models";
import { AuditEvent } from "utils/hooks/useAlerts";
import { getInitials } from "@/components/navbar/UserAvatar";

const formatTimestamp = (timestamp: Date | string) => {
  const date = new Date(timestamp);
  return date.toLocaleString();
};

type AlertTimelineProps = {
  alert: AlertDto | null;
  auditData: AuditEvent[];
  isLoading: boolean;
  onRefresh: () => void;
};

const AlertTimeline: React.FC<AlertTimelineProps> = ({
  alert,
  auditData,
  isLoading,
  onRefresh,
}) => {
  // Default audit event if no audit data is available
  const defaultAuditEvent = alert
    ? [
        {
          user_id: "system",
          action: "Alert is triggered",
          description: "alert received from provider with status firing",
          timestamp: alert.lastReceived,
        },
      ]
    : [];

  const auditContent = auditData?.length ? auditData : defaultAuditEvent;
  const content = auditContent.map((entry, index) => (
    <div
      key={index}
      className="flex items-start space-x-4 ml-6"
      style={{ width: "400px" }}
    >
      {entry.user_id.toLowerCase() === "system" ? (
        <Image
          src="/icons/keep-icon.png"
          alt="Keep Logo"
          width={40}
          height={40}
          className="rounded-full flex-shrink-0"
        />
      ) : (
        <span className="relative inline-flex items-center justify-center w-10 h-10 overflow-hidden bg-orange-400 rounded-full flex-shrink-0">
          <span className="font-medium text-white text-xs">
            {getInitials(entry.user_id)}
          </span>
        </span>
      )}
      <div className="flex flex-col justify-center flex-grow overflow-hidden">
        <Subtitle className="text-sm text-orange-500 font-semibold whitespace-normal overflow-wrap-break-word">
          {entry.action.toLowerCase()}
        </Subtitle>
        <Subtitle className="text-xs whitespace-normal overflow-wrap-break-word">
          {entry.description.toLowerCase()}
        </Subtitle>
      </div>
    </div>
  ));

  return (
    <div className="max-h-[500px] overflow-y-auto">
      <div className="flex justify-between items-center">
        <Subtitle>Timeline</Subtitle>
        <Button
          icon={ArrowPathIcon}
          color="orange"
          size="xs"
          disabled={isLoading}
          loading={isLoading}
          onClick={onRefresh}
          title="Refresh"
        />
      </div>
      {isLoading ? (
        <div className="flex justify-center items-center h-full">
          <p>Loading...</p>
        </div>
      ) : (
        <div className="flex-grow">
          <Chrono
            items={
              auditContent.map((entry) => ({
                title: formatTimestamp(entry.timestamp),
              })) || []
            }
            hideControls
            disableToolbar
            borderLessCards
            slideShow={false}
            mode="VERTICAL"
            theme={{
              primary: "orange",
              secondary: "rgb(255 247 237)",
              titleColor: "orange",
              titleColorActive: "orange",
            }}
            fontSizes={{
              title: ".75rem",
            }}
            cardWidth={400}
            cardHeight="auto"
            classNames={{
              card: "hidden",
              cardMedia: "hidden",
              cardSubTitle: "hidden",
              cardText: "hidden",
              cardTitle: "hidden",
              title: "mb-3",
              contentDetails: "w-full !m-0",
            }}
          >
            {content}
          </Chrono>
        </div>
      )}
    </div>
  );
};

export default AlertTimeline;
