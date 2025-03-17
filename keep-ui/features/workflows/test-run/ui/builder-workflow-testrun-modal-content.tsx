import { Title } from "@tremor/react";
import {
  isWorkflowExecution,
  WorkflowExecutionDetail,
  WorkflowExecutionFailure,
} from "@/shared/api/workflow-executions";
import { WorkflowExecutionResults } from "@/features/workflow-execution-results";
import { IoClose } from "react-icons/io5";
import { KeepLoader } from "@/shared/ui";

interface Props {
  closeModal: () => void;
  workflowId: string;
  workflowExecution: WorkflowExecutionDetail | WorkflowExecutionFailure | null;
}

export function BuilderWorkflowTestRunModalContent({
  closeModal,
  workflowId,
  workflowExecution,
}: Props) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <div>
          <Title>Workflow Execution Results</Title>
        </div>
        <div>
          <button onClick={closeModal}>
            <IoClose size={20} />
          </button>
        </div>
      </div>
      <div className="flex flex-col">
        {workflowExecution ? (
          <WorkflowExecutionResults
            workflowId={workflowId}
            initialWorkflowExecution={workflowExecution}
            workflowExecutionId={
              isWorkflowExecution(workflowExecution)
                ? workflowExecution.id
                : null
            }
          />
        ) : (
          <div className="flex justify-center">
            <KeepLoader loadingText="Loading workflow execution results..." />
          </div>
        )}
      </div>
    </div>
  );
}
