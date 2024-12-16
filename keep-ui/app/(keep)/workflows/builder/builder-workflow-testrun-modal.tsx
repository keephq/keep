import { XMarkIcon } from "@heroicons/react/24/outline";
import { Button, Card, Subtitle, Title } from "@tremor/react";
import ReactLoading from "react-loading";
import { ExecutionResults } from "./workflow-execution-results";
import { WorkflowExecution, WorkflowExecutionFailure } from "./types";
import { ApiClient } from "@/shared/api";

interface Props {
  closeModal: () => void;
  workflowExecution: WorkflowExecution | WorkflowExecutionFailure | null;
  apiClient: ApiClient;
}

export default function BuilderWorkflowTestRunModalContent({
  closeModal,
  workflowExecution,
  apiClient,
}: Props) {
  return (
    <>
      <div className="flex justify-between items-center">
        <div>
          <Title>Workflow Execution Results</Title>
        </div>
        <div>
          <Button
            color="orange"
            className="w-36"
            icon={XMarkIcon}
            onClick={closeModal}
            size="xs"
          >
            Close
          </Button>
        </div>
      </div>
      <Card className={`p-4 md:p-10 mx-auto max-w-7xl mt-6 h-full`}>
        <div className="flex flex-col">
          {workflowExecution ? (
            <ExecutionResults
              executionData={workflowExecution}
              api={apiClient}
            />
          ) : (
            <div className="flex justify-center">
              <ReactLoading
                type="spin"
                color="rgb(234 160 112)"
                height={50}
                width={50}
              />
            </div>
          )}
        </div>
      </Card>
    </>
  );
}
