"use client";

import { Button, Callout, Text, Title } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { useEffect, useState } from "react";
import { IncidentDto } from "@/entities/incidents/model";
import { AlertDto } from "@/entities/alerts/model";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { Select } from "@/shared/ui";
import { Trigger, Workflow } from "@/shared/api/workflows";
import { components, OptionProps } from "react-select";
import { FilterOptionOption } from "react-select/dist/declarations/src/filters";
import { WorkflowTriggerBadge } from "@/entities/workflows/ui/WorkflowTriggerBadge";
import Link from "next/link";
import {
  DEFAULT_WORKFLOWS_QUERY,
  useWorkflowsV2,
} from "@/entities/workflows/model/useWorkflowsV2";
import {
  WorkflowInputFields,
  areRequiredInputsFilled,
} from "@/entities/workflows/ui/WorkflowInputFields";
import { parseWorkflowYamlToJSON } from "@/entities/workflows/lib/yaml-utils";
import { InfoCircledIcon } from "@radix-ui/react-icons";
import {
  YamlWorkflowDefinitionSchema,
  type WorkflowInput,
} from "@/entities/workflows/model/yaml.schema";

interface Props {
  alert?: AlertDto | null | undefined;
  incident?: IncidentDto | null | undefined;
  workflow?: Workflow | null | undefined;
  onClose: () => void;
  isOpen?: boolean;
  onSubmit?: ({ inputs }: { inputs: Record<string, any> }) => void;
}

export function ManualRunWorkflowModal({
  alert,
  incident,
  workflow,
  onClose,
  isOpen: propIsOpen,
  onSubmit,
}: Props) {
  const [selectedWorkflow, setSelectedWorkflow] = useState<
    Workflow | undefined
  >(undefined);
  const [workflowInputs, setWorkflowInputs] = useState<WorkflowInput[]>([]);
  const [inputValues, setInputValues] = useState<Record<string, any>>({});
  const { workflows } = useWorkflowsV2({
    ...DEFAULT_WORKFLOWS_QUERY,
    limit: 100, // Fetch more workflows at once for the dropdown
    cel: "disabled == false", // Only show enabled workflows
  });
  const filteredWorkflows = workflows?.filter((w) => w.canRun);
  const api = useApi();

  // If isOpen is provided as a prop, use it; otherwise, derive from alert/incident
  const isOpen = propIsOpen !== undefined ? propIsOpen : !!alert || !!incident;
  const effectiveWorkflow = workflow || selectedWorkflow;

  useEffect(() => {
    if (workflow) {
      // If workflow is directly provided, use it
      setSelectedWorkflow(workflow);
    }
  }, [workflow]);

  useEffect(() => {
    if (effectiveWorkflow?.workflow_raw) {
      try {
        // Parse workflow_raw as YAML to extract inputs
        const parsedWorkflow = parseWorkflowYamlToJSON(
          effectiveWorkflow.workflow_raw,
          YamlWorkflowDefinitionSchema
        );
        const inputs = parsedWorkflow.data?.workflow.inputs;
        if (!inputs) {
          return;
        }

        // Add visual indicator of required status for inputs without defaults
        const enhancedInputs = inputs.map((input) => {
          // Mark inputs without defaults as visually required
          if (input.default === undefined && !input.required) {
            return { ...input, visuallyRequired: true };
          }
          return input;
        });

        setWorkflowInputs(enhancedInputs);

        // Initialize input values with defaults
        const initialValues: Record<string, any> = {};
        inputs.forEach((input) => {
          initialValues[input.name] =
            input.default !== undefined ? input.default : "";
        });
        setInputValues(initialValues);
      } catch (error) {
        console.error("Failed to parse workflow_raw:", error);
        setWorkflowInputs([]);
        setInputValues({});
      }
    } else {
      setWorkflowInputs([]);
      setInputValues({});
    }
  }, [effectiveWorkflow]);

  const clearAndClose = () => {
    if (!workflow) {
      // Only reset selected workflow if it wasn't passed as a prop
      setSelectedWorkflow(undefined);
    }
    setWorkflowInputs([]);
    setInputValues({});
    onClose();
  };

  const handleInputChange = (name: string, value: any) => {
    setInputValues((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleRun = async () => {
    try {
      if (onSubmit) {
        // If onSubmit prop is provided, use it (for WorkflowDetailHeader usage)
        onSubmit({ inputs: inputValues });
      } else if (effectiveWorkflow) {
        // Direct API call for alert/incident context
        const responseData = await api.post(
          `/workflows/${effectiveWorkflow.id}/run`,
          {
            type: alert ? "alert" : "incident",
            body: alert ? alert : incident,
            inputs: inputValues, // Include user inputs in the request
          }
        );

        const { workflow_execution_id } = responseData;
        const executionUrl = `/workflows/${effectiveWorkflow.id}/runs/${workflow_execution_id}`;

        showSuccessToast(
          <div>
            Workflow started successfully.{" "}
            <Link
              href={executionUrl}
              className="text-orange-500 hover:text-orange-600 underline"
              onClick={(e) => {
                e.stopPropagation();
              }}
            >
              View execution
            </Link>
          </div>
        );
      }
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
      className="overflow-visible max-w-xl w-full"
      beforeTitle={
        alert?.name ||
        (effectiveWorkflow?.name ? `Run: ${effectiveWorkflow.name}` : undefined)
      }
      title={workflow ? "Run Workflow with Inputs" : "Run Workflow"}
    >
      {/* Only show workflow selector when no workflow is directly provided */}
      {!workflow && (
        <>
          {filteredWorkflows && filteredWorkflows.length > 0 ? (
            <div>
              {filteredWorkflows.length !== workflows?.length && (
                <Callout
                  title="For your information"
                  color="yellow"
                  className="mb-2 text-xs"
                  icon={InfoCircledIcon}
                >
                  Some workflows are not visible to you because you lack
                  permissions.
                </Callout>
              )}
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
                    workflow.name.toLowerCase().indexOf(query.toLowerCase()) >
                      -1 ||
                    workflow.description
                      .toLowerCase()
                      .indexOf(query.toLowerCase()) > -1 ||
                    workflow.id.toLowerCase().indexOf(query.toLowerCase()) > -1
                  );
                }}
                components={{
                  Option: CustomOption,
                }}
                options={filteredWorkflows}
              />
            </div>
          ) : (
            <span className="text-gray-500 text-sm">No workflows found</span>
          )}
        </>
      )}

      {/* Always show workflow inputs when available - whether from direct workflow or selected workflow */}
      {workflowInputs.length > 0 ? (
        <div className="mt-4">
          <Text className="font-bold">
            Fill in the inputs required to run the workflow
          </Text>
          <WorkflowInputFields
            workflowInputs={workflowInputs}
            inputValues={inputValues}
            onInputChange={handleInputChange}
          />
        </div>
      ) : effectiveWorkflow ? (
        <div className="mt-4 text-center py-4">
          <Text>This workflow does not require any inputs</Text>
        </div>
      ) : null}

      <div className="flex justify-end gap-2 mt-4">
        <Button onClick={clearAndClose} color="orange" variant="secondary">
          Cancel
        </Button>
        <Button
          onClick={handleRun}
          color="orange"
          disabled={
            !effectiveWorkflow ||
            (workflowInputs.length > 0 &&
              !areRequiredInputsFilled(workflowInputs, inputValues))
          }
        >
          Run
        </Button>
      </div>
    </Modal>
  );
}
