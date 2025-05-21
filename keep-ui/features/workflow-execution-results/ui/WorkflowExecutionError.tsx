import { Link } from "@/components/ui/Link";
import { WorkflowExecutionDetail } from "@/shared/api/workflow-executions";
import { DOCS_CLIPBOARD_COPY_ERROR_PATH } from "@/shared/constants";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { showSuccessToast } from "@/shared/ui";
import { useConfig } from "@/utils/hooks/useConfig";
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
  const { data: config } = useConfig();

  const getCurlCommand = () => {
    let token = api.getToken();
    let url = api.getApiBaseUrl();
    // Only include workflow ID if workflowData is available
    const workflowIdParam = workflowId ? `/${workflowId}` : "";
    return `curl -X POST "${url}/workflows${workflowIdParam}/run?event_type=${eventType}&event_id=${eventId}" \\
  -H "Authorization: Bearer ${token}" \\
  -H "Content-Type: application/json"`;
  };

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(getCurlCommand());
      showSuccessToast("CURL command copied to clipboard");
    } catch (err) {
      showErrorToast(
        err,
        <p>
          Failed to copy CURL command. Please check your browser permissions.{" "}
          <Link
            target="_blank"
            href={`${config?.KEEP_DOCS_URL}${DOCS_CLIPBOARD_COPY_ERROR_PATH}`}
          >
            Learn more
          </Link>
        </p>
      );
    }
  };

  return (
    <Callout
      title="Error during workflow execution"
      icon={ExclamationCircleIcon}
      color="rose"
      className="shrink-0"
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
