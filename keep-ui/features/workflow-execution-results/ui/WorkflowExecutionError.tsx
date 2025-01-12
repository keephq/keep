import { WorkflowExecutionDetail } from "@/shared/api/workflow-executions";
import { useApi } from "@/shared/lib/hooks/useApi";
import { ExclamationCircleIcon } from "@heroicons/react/20/solid";
import { Button, Callout } from "@tremor/react";

export function WorkflowExecutionError({
  error,
  workflowId,
  eventId,
  eventType,
}: {
  error: WorkflowExecutionDetail["error"];
  workflowId: string | undefined;
  eventId: string | undefined;
  eventType: string | undefined;
}) {
  const api = useApi();

  const getCurlCommand = () => {
    let token = api.getToken();
    let url = api.getApiBaseUrl();
    // Only include workflow ID if workflowData is available
    const workflowIdParam = workflowId ? `/${workflowId}` : "";
    return `curl -X POST "${url}/workflows${workflowIdParam}/run?event_type=${eventType}&event_id=${eventId}" \\
  -H "Authorization: Bearer ${token}" \\
  -H "Content-Type: application/json"`;
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(getCurlCommand());
  };

  return (
    <Callout
      title="Error during workflow execution"
      icon={ExclamationCircleIcon}
      color="rose"
    >
      <div className="flex justify-between items-center">
        <div>
          {error?.split("\n").map((line, index) => <p key={index}>{line}</p>)}
        </div>
        {eventId && eventType && (
          <Button color="rose" onClick={copyToClipboard}>
            Copy CURL replay
          </Button>
        )}
      </div>
    </Callout>
  );
}
