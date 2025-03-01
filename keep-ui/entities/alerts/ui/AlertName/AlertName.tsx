import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  ArrowTopRightOnSquareIcon,
  BookOpenIcon,
  TicketIcon,
  TrashIcon,
  PencilSquareIcon,
  Cog8ToothIcon,
} from "@heroicons/react/24/outline";
import { Icon } from "@tremor/react";
import { AlertDto, AlertToWorkflowExecution } from "@/entities/alerts/model";
import { useRouter } from "next/navigation";
import { useWorkflowExecutions } from "@/utils/hooks/useWorkflowExecutions";
import { useLocalStorage } from "utils/hooks/useLocalStorage";

// Define the tooltip position type
type TooltipPosition = { x: number; y: number } | null;

// Component to render the image preview tooltip
const ImagePreviewTooltip = ({
  imageUrl,
  position,
}: {
  imageUrl: string;
  position: TooltipPosition;
}) => {
  if (!position) return null;

  return createPortal(
    <div
      className="absolute shadow-lg rounded border border-gray-100 z-50"
      style={{
        left: position.x,
        top: position.y,
        pointerEvents: "none",
      }}
    >
      <div className="p-1 bg-gray-200">
        <img
          src={imageUrl}
          alt="Preview"
          className="max-w-xs max-h-64 object-contain"
        />
      </div>
    </div>,
    document.body
  );
};

interface Props {
  alert: AlertDto;
  setNoteModalAlert?: (alert: AlertDto) => void;
  setTicketModalAlert?: (alert: AlertDto) => void;
  className?: string;
}

export function AlertName({
  alert,
  setNoteModalAlert,
  setTicketModalAlert,
  className,
}: Props) {
  const router = useRouter();
  const { data: executions } = useWorkflowExecutions();
  const [imageError, setImageError] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition>(null);
  const imageContainerRef = useRef<HTMLDivElement | null>(null);
  const [rowStyle] = useLocalStorage("alert-table-row-style", "default");

  const handleNoteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (setNoteModalAlert) {
      setNoteModalAlert(alert);
    }
  };

  const handleTicketClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!ticketUrl && setTicketModalAlert) {
      setTicketModalAlert(alert);
    } else {
      window.open(ticketUrl, "_blank");
    }
  };

  const handleImageClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (imageUrl) {
      window.open(imageUrl, "_blank");
    }
  };

  const handleMouseEnter = () => {
    if (imageContainerRef.current && !imageError) {
      const rect = imageContainerRef.current.getBoundingClientRect();
      setTooltipPosition({
        x: rect.right + 10,
        y: rect.top - 150,
      });
    }
  };

  const handleMouseLeave = () => {
    setTooltipPosition(null);
  };

  // Update tooltip position on scroll to ensure it stays with the thumbnail
  useEffect(() => {
    const handleScroll = () => {
      if (tooltipPosition && imageContainerRef.current) {
        const rect = imageContainerRef.current.getBoundingClientRect();
        setTooltipPosition({
          x: rect.right + 10,
          y: rect.top - 150,
        });
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [tooltipPosition]);

  const relevantWorkflowExecution = executions?.find(
    (wf) => wf.event_id === alert.event_id
  );

  const {
    name,
    url,
    generatorURL,
    deleted,
    note,
    ticket_url: ticketUrl,
    ticket_status: ticketStatus,
    playbook_url,
    imageUrl,
  } = alert;

  function handleWorkflowClick(
    e: React.MouseEvent,
    relevantWorkflowExecution: AlertToWorkflowExecution
  ) {
    e.stopPropagation();
    router.push(
      `/workflows/${relevantWorkflowExecution.workflow_id}/runs/${relevantWorkflowExecution.workflow_execution_id}`
    );
  }

  const isDense = rowStyle === "dense";

  return (
    <div
      className={`flex items-center justify-between w-full ${className || ""}`}
    >
      <div
        className={`${
          isDense
            ? "truncate whitespace-nowrap"
            : "line-clamp-3 whitespace-pre-wrap"
        } flex-grow`}
        title={alert.name}
      >
        {name}
      </div>
      <div
        className={`flex items-center ml-2 ${
          isDense ? "flex-shrink-0" : ""
        } prevent-row-click`}
      >
        {(url ?? generatorURL) && (
          <a
            href={url || generatorURL}
            target="_blank"
            onClick={(e) => e.stopPropagation()}
            className="prevent-row-click"
          >
            <Icon
              icon={ArrowTopRightOnSquareIcon}
              tooltip="Open Original Alert"
              color="green"
              variant="solid"
              size="xs"
              className="ml-1 prevent-row-click"
            />
          </a>
        )}

        {setTicketModalAlert && (
          <Icon
            icon={TicketIcon}
            tooltip={
              ticketUrl
                ? `Ticket Assigned ${
                    ticketStatus ? `(status: ${ticketStatus})` : ""
                  }`
                : "Click to assign Ticket"
            }
            size="xs"
            color={ticketUrl ? "green" : "gray"}
            className="ml-1 cursor-pointer prevent-row-click"
            variant="solid"
            onClick={handleTicketClick}
          />
        )}

        {playbook_url && (
          <a
            href={playbook_url}
            target="_blank"
            onClick={(e) => e.stopPropagation()}
            className="prevent-row-click"
          >
            <Icon
              icon={BookOpenIcon}
              tooltip="Playbook"
              size="xs"
              color="gray"
              className="ml-1 prevent-row-click"
              variant="solid"
            />
          </a>
        )}

        {setNoteModalAlert && (
          <Icon
            icon={PencilSquareIcon}
            tooltip="Click to add note"
            size="xs"
            color={note ? "green" : "gray"}
            className="ml-1 cursor-pointer prevent-row-click"
            variant="solid"
            onClick={handleNoteClick}
          />
        )}

        {deleted && (
          <Icon
            icon={TrashIcon}
            tooltip="This alert has been deleted"
            size="xs"
            color="gray"
            className="ml-1 prevent-row-click"
            variant="solid"
          />
        )}

        {relevantWorkflowExecution && (
          <Icon
            icon={Cog8ToothIcon}
            size="xs"
            color={`${
              relevantWorkflowExecution.workflow_status === "success"
                ? "green"
                : relevantWorkflowExecution.workflow_status === "error"
                ? "red"
                : "gray"
            }`}
            tooltip={`${
              relevantWorkflowExecution.workflow_status === "success"
                ? "Last workflow executed successfully"
                : relevantWorkflowExecution.workflow_status === "error"
                ? "Last workflow execution failed"
                : undefined
            }`}
            onClick={(e) => handleWorkflowClick(e, relevantWorkflowExecution)}
            className="ml-1 cursor-pointer prevent-row-click"
            variant="solid"
          />
        )}

        {imageUrl && !imageError && (
          <div
            ref={imageContainerRef}
            className="ml-1 rounded bg-gray-200 border border-gray-200 p-1 flex items-center justify-center cursor-pointer relative hover:bg-gray-300 transition-all duration-150 prevent-row-click"
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            onClick={handleImageClick}
            style={{ width: "28px", height: "28px" }}
          >
            <img
              src={imageUrl}
              alt="Preview"
              className="h-5 w-5 object-cover rounded prevent-row-click"
              onError={() => setImageError(true)}
            />
          </div>
        )}

        {tooltipPosition && imageUrl && !imageError && (
          <ImagePreviewTooltip imageUrl={imageUrl} position={tooltipPosition} />
        )}
      </div>
    </div>
  );
}
