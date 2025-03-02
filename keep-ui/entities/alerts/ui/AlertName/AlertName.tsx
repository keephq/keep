import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  ArrowTopRightOnSquareIcon,
  BookOpenIcon,
  TicketIcon,
  TrashIcon,
  PencilSquareIcon,
  Cog8ToothIcon,
  EyeIcon,
} from "@heroicons/react/24/outline";
import { Icon } from "@tremor/react";
import { AlertDto, AlertToWorkflowExecution } from "@/entities/alerts/model";
import { useRouter } from "next/navigation";
import { useWorkflowExecutions } from "@/utils/hooks/useWorkflowExecutions";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { clsx } from "clsx";

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
  const [showActionsOnHover] = useLocalStorage("alert-action-tray-hover", true);

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

      <div className="flex items-center h-full pl-2">
        <div
          className={clsx(
            "flex items-center gap-1 transition-all duration-200",
            showActionsOnHover
              ? [
                  "transform translate-x-2 opacity-0",
                  "group-hover/row:translate-x-0 group-hover/row:opacity-100",
                ]
              : "opacity-100"
          )}
        >
          {(url ?? generatorURL) && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                window.open(url || generatorURL, "_blank");
              }}
              className="p-1.5 hover:bg-gray-100 rounded-md transition-colors prevent-row-click"
              title="Open Original Alert"
            >
              <Icon
                icon={ArrowTopRightOnSquareIcon}
                size="sm"
                className="text-gray-500"
              />
            </button>
          )}

          {setTicketModalAlert && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleTicketClick(e);
              }}
              className="p-1.5 hover:bg-gray-100 rounded-md transition-colors prevent-row-click"
              title={
                ticketUrl
                  ? `Ticket Assigned ${
                      ticketStatus ? `(status: ${ticketStatus})` : ""
                    }`
                  : "Click to assign Ticket"
              }
            >
              <Icon
                icon={TicketIcon}
                size="sm"
                className={`text-${ticketUrl ? "green" : "gray"}-500`}
              />
            </button>
          )}

          {playbook_url && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                window.open(playbook_url, "_blank");
              }}
              className="p-1.5 hover:bg-gray-100 rounded-md transition-colors prevent-row-click"
              title="View Playbook"
            >
              <Icon icon={BookOpenIcon} size="sm" className="text-gray-500" />
            </button>
          )}

          {setNoteModalAlert && (
            <button
              onClick={(e) => handleNoteClick(e)}
              className="p-1.5 hover:bg-gray-100 rounded-md transition-colors prevent-row-click"
              title="Add/Edit Note"
            >
              <Icon
                icon={PencilSquareIcon}
                size="sm"
                className={`text-${note ? "green" : "gray"}-500`}
              />
            </button>
          )}

          {relevantWorkflowExecution && (
            <button
              onClick={(e) => handleWorkflowClick(e, relevantWorkflowExecution)}
              className="p-1.5 hover:bg-gray-100 rounded-md transition-colors prevent-row-click"
              title={`Workflow ${relevantWorkflowExecution.workflow_status}`}
            >
              <Icon
                icon={Cog8ToothIcon}
                size="sm"
                className={`text-${
                  relevantWorkflowExecution.workflow_status === "success"
                    ? "green"
                    : relevantWorkflowExecution.workflow_status === "error"
                    ? "red"
                    : "gray"
                }-500`}
              />
            </button>
          )}

          {imageUrl && !imageError && (
            <div
              ref={imageContainerRef}
              className="p-1.5 hover:bg-gray-100 rounded-md transition-colors prevent-row-click"
              onMouseEnter={handleMouseEnter}
              onMouseLeave={handleMouseLeave}
              onClick={handleImageClick}
              title="View Image"
            >
              <img
                src={imageUrl}
                alt="Preview"
                className="h-4 w-4 object-cover rounded prevent-row-click"
                onError={() => setImageError(true)}
              />
            </div>
          )}
        </div>
      </div>

      {tooltipPosition && imageUrl && !imageError && (
        <ImagePreviewTooltip imageUrl={imageUrl} position={tooltipPosition} />
      )}
    </div>
  );
}
