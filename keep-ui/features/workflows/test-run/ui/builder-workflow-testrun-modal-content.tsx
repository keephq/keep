import { XMarkIcon } from "@heroicons/react/24/outline";
import { Button, Title } from "@tremor/react";
import ReactLoading from "react-loading";
import {
  isWorkflowExecution,
  WorkflowExecutionDetail,
  WorkflowExecutionFailure,
} from "@/shared/api/workflow-executions";
import { WorkflowExecutionResults } from "@/features/workflow-execution-results";
import { IoClose } from "react-icons/io5";

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
            <ReactLoading
              type="spin"
              color="rgb(234 160 112)"
              height={50}
              width={50}
            />
          </div>
        )}
      </div>
    </div>
  );
}
