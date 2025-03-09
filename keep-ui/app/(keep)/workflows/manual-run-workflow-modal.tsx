import { Button, Text, Title } from "@tremor/react";

import Modal from "@/components/ui/Modal";
import { useWorkflows } from "utils/hooks/useWorkflows";
import { useState } from "react";
import { toast } from "react-toastify";
import { useRouter } from "next/navigation";
import { IncidentDto } from "@/entities/incidents/model";
import { AlertDto } from "@/entities/alerts/model";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Select, showErrorToast } from "@/shared/ui";
import { Trigger, Workflow } from "@/shared/api/workflows";
import { components, OptionProps } from "react-select";
import { FilterOptionOption } from "react-select/dist/declarations/src/filters";
import { WorkflowTriggerBadge } from "@/entities/workflows/ui/WorkflowTriggerBadge";

interface Props {
  alert?: AlertDto | null | undefined;
  incident?: IncidentDto | null | undefined;
  handleClose: () => void;
}

export default function ManualRunWorkflowModal({
  alert,
  incident,
  handleClose,
}: Props) {
  /**
   *
   */
  const [selectedWorkflow, setSelectedWorkflow] = useState<
    Workflow | undefined
  >(undefined);
  const { data: workflows } = useWorkflows();
  const api = useApi();
  const router = useRouter();

  const isOpen = !!alert || !!incident;

  const clearAndClose = () => {
    setSelectedWorkflow(undefined);
    handleClose();
  };

  const handleRun = async () => {
    try {
      const responseData = await api.post(
        `/workflows/${selectedWorkflow?.id}/run`,
        {
          type: alert ? "alert" : "incident",
          body: alert ? alert : incident,
        }
      );

      const { workflow_execution_id } = responseData;
      const executionUrl = `/workflows/${selectedWorkflow?.id}/runs/${workflow_execution_id}`;

      toast.success(
        <div>
          Workflow started successfully.{" "}
          <a
            href={executionUrl}
            className="text-orange-500 hover:text-orange-600 underline"
            onClick={(e) => {
              e.preventDefault();
              router.push(executionUrl);
            }}
          >
            View execution
          </a>
        </div>,
        { position: "top-right" }
      );
    } catch (error) {
      showErrorToast(error, "Failed to start workflow");
    }
    clearAndClose();
  };

  const WorkflowSelect = (props: any) => {
    return <Select<Workflow> {...props} />;
  };

  const CustomOption = (props: OptionProps<Workflow>) => {
    const workflow: Workflow = props.data;

    return (
      <components.Option {...props}>
        <div className="flex justify-between">
          <Title className="max-w-[300px] overflow-ellipsis">
            {workflow.name}
          </Title>
          <small>by {workflow.created_by}</small>
        </div>
        <Text>{workflow.description}</Text>
        <div className="pt-2 flex gap-1">
          {workflow.triggers.map((trigger: Trigger) => (
            <WorkflowTriggerBadge
              key={trigger.type}
              trigger={trigger}
              showTooltip={false}
              // Do nothing, but not undefined to allow click
              // but just propagate it to parent elemennt
              onClick={() => {}}
            />
          ))}
        </div>
      </components.Option>
    );
  };

  return (
    <Modal
      onClose={clearAndClose}
      isOpen={isOpen}
      className="overflow-visible"
      beforeTitle={alert?.name}
      title="Run Workflow"
    >
      <Text className="mb-1 mt-4">Select workflow to run</Text>
      {workflows ? (
        <WorkflowSelect
          placeholder="Select workflow"
          value={selectedWorkflow}
          getOptionValue={(w: any) => w.id}
          getOptionLabel={(workflow: Workflow) =>
            `${workflow.name} (${workflow.description})`
          }
          onChange={setSelectedWorkflow}
          filterOption={(
            { data: workflow }: FilterOptionOption<Workflow>,
            query: string
          ) => {
            if (query === "") {
              return true;
            }
            return (
              workflow.name.toLowerCase().indexOf(query.toLowerCase()) > -1 ||
              workflow.description.toLowerCase().indexOf(query.toLowerCase()) >
                -1 ||
              workflow.id.toLowerCase().indexOf(query.toLowerCase()) > -1
            );
          }}
          components={{
            Option: CustomOption,
          }}
          options={workflows.filter((workflow) => !workflow.disabled)}
        />
      ) : (
        <div>No workflows found</div>
      )}
      <div className="flex justify-end gap-2 mt-4">
        <Button onClick={clearAndClose} color="orange" variant="secondary">
          Cancel
        </Button>
        <Button onClick={handleRun} color="orange" disabled={!selectedWorkflow}>
          Run
        </Button>
      </div>
    </Modal>
  );
}
