import { Title } from "@tremor/react";
import { WorkflowExecutionResults } from "@/features/workflow-execution-results";
import { IoClose } from "react-icons/io5";

interface Props {
  closeModal: () => void;
  workflowId: string;
  workflowExecutionId: string;
  workflowYamlSent: string | null;
}

export function BuilderWorkflowTestRunModalContent({
  closeModal,
  workflowId,
  workflowExecutionId,
  workflowYamlSent,
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
        <WorkflowExecutionResults
          workflowId={workflowId}
          workflowExecutionId={workflowExecutionId}
          workflowYaml={workflowYamlSent ?? ""}
        />
      </div>
    </div>
  );
}
