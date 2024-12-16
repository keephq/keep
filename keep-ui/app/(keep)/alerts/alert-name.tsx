import {
  ArrowTopRightOnSquareIcon,
  BookOpenIcon,
  TicketIcon,
  TrashIcon,
  PencilSquareIcon,
  // Cog8ToothIcon,
} from "@heroicons/react/24/outline";
import { Icon } from "@tremor/react";
import { AlertDto, AlertToWorkflowExecution } from "./models";
// import { useWorkflowExecutions } from "utils/hooks/useWorkflowExecutions";
import { useRouter } from "next/navigation";

interface Props {
  alert: AlertDto;
  setNoteModalAlert?: (alert: AlertDto) => void;
  setTicketModalAlert?: (alert: AlertDto) => void;
}
export default function AlertName({
  alert,
  setNoteModalAlert,
  setTicketModalAlert,
}: Props) {
  const router = useRouter();
  // TODO: fix this so we can show which alert had workflow execution
  // const { data: executions } = useWorkflowExecutions();

  const handleNoteClick = () => {
    if (setNoteModalAlert) {
      setNoteModalAlert(alert);
    }
  };

  const handleTicketClick = () => {
    if (!ticketUrl && setTicketModalAlert) {
      setTicketModalAlert(alert);
    } else {
      window.open(ticketUrl, "_blank"); // Open the ticket URL in a new tab
    }
  };

  const relevantWorkflowExecution: AlertToWorkflowExecution | null = null;
  // executions?.find((wf) => wf.alert_fingerprint === alert.fingerprint) ??
  // null;

  const {
    name,
    url,
    generatorURL,
    deleted,
    note,
    ticket_url: ticketUrl,
    ticket_status: ticketStatus,
    playbook_url,
  } = alert;

  function handleWorkflowClick(
    relevantWorkflowExecution: AlertToWorkflowExecution
  ): void {
    router.push(
      `/workflows/${relevantWorkflowExecution.workflow_id}/runs/${relevantWorkflowExecution.workflow_execution_id}`
    );
  }

  return (
    <div className="flex items-center justify-between">
      <div className="line-clamp-3 whitespace-pre-wrap" title={alert.name}>
        {name}
      </div>
      <div className="flex-shrink-0">
        {(url ?? generatorURL) && (
          <a href={url || generatorURL} target="_blank">
            <Icon
              icon={ArrowTopRightOnSquareIcon}
              tooltip="Open Original Alert"
              color="green"
              variant="solid"
              size="xs"
              className="ml-1"
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
            className="ml-1 cursor-pointer"
            variant="solid"
            onClick={handleTicketClick}
          />
        )}

        {playbook_url && (
          <a href={playbook_url} target="_blank">
            <Icon
              icon={BookOpenIcon}
              tooltip="Playbook"
              size="xs"
              color="gray"
              className="ml-1"
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
            className="ml-1 cursor-pointer"
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
            className="ml-1"
            variant="solid"
          />
        )}
        {/* {relevantWorkflowExecution && (
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
            onClick={() => handleWorkflowClick(relevantWorkflowExecution)}
            className="ml-1 cursor-pointer"
            variant="solid"
          />
        )} */}
      </div>
    </div>
  );
}
