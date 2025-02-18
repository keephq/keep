"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import WorkflowMenu from "./workflow-menu";
import { KeepLoader } from "@/shared/ui";
import { Trigger, Workflow } from "@/shared/api/workflows";
import {
  Button,
  Card,
  Icon,
  ListItem,
  List,
  Badge,
  Title,
} from "@tremor/react";
import {
  CheckCircleIcon,
  ClockIcon,
  CursorArrowRaysIcon,
} from "@heroicons/react/24/outline";
import AlertTriggerModal from "./workflow-run-with-alert-modal";
import { formatDistanceToNowStrict } from "date-fns";
import TimeAgo, { Formatter, Suffix, Unit } from "react-timeago";
import WorkflowGraph from "./workflow-graph";
import Modal from "@/components/ui/Modal";
import { HiBellAlert } from "react-icons/hi2";
import { useWorkflowRun } from "utils/hooks/useWorkflowRun";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useToggleWorkflow } from "utils/hooks/useWorkflowToggle";
import "./workflow-tile.css";
import { WorkflowTriggerBadge } from "@/entities/workflows/ui/WorkflowTriggerBadge";

function TriggerTile({ trigger }: { trigger: Trigger }) {
  return (
    <ListItem>
      <WorkflowTriggerBadge trigger={trigger} />
      {trigger.type === "manual" && (
        <span>
          <Icon icon={CheckCircleIcon} color="green" className="p-0" />
        </span>
      )}
      {trigger.type === "interval" && <span>{trigger.value} seconds</span>}
      {trigger.type === "alert" && (
        <span className="text-sm text-right">
          {trigger.filters &&
            trigger.filters.map((filter) => (
              <>
                {filter.key} = {filter.value}
              </>
            ))}
        </span>
      )}
    </ListItem>
  );
}

function WorkflowTile({ workflow }: { workflow: Workflow }) {
  // Create a set to keep track of unique providers
  const router = useRouter();

  const [openTriggerModal, setOpenTriggerModal] = useState<boolean>(false);
  const alertSource = workflow?.triggers
    ?.find((w) => w.type === "alert")
    ?.filters?.find((f) => f.key === "source")?.value;
  const [fallBackIcon, setFallBackIcon] = useState(false);
  const { toggleWorkflow } = useToggleWorkflow(workflow.id);

  const { deleteWorkflow } = useWorkflowActions();
  const {
    isRunning,
    handleRunClick,
    getTriggerModalProps,
    isRunButtonDisabled,
    message,
  } = useWorkflowRun(workflow!);

  const handleDeleteClick = async () => {
    deleteWorkflow(workflow.id);
  };

  const handleWorkflowClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    const target = e.target as HTMLElement;
    if (target.closest(".js-dont-propagate")) {
      // do not redirect if the three-dot menu is clicked
      return;
    }
    router.push(`/workflows/${workflow.id}`);
  };

  const handleDownloadClick = async () => {
    try {
      // Use the raw workflow data directly, as it is already in YAML format
      const workflowYAML = workflow.workflow_raw;

      // Create a Blob object representing the data as a YAML file
      const blob = new Blob([workflowYAML], { type: "text/yaml" });

      // Create an anchor element with a URL object created from the Blob
      const url = window.URL.createObjectURL(blob);

      // Create a "hidden" anchor tag with the download attribute and click it
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = `${workflow.workflow_raw_id}.yaml`; // The file will be named after the workflow's id
      document.body.appendChild(a);
      a.click();

      // Release the object URL to free up resources
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("An error occurred while downloading the YAML", error);
    }
  };

  const handleViewClick = async () => {
    router.push(`/workflows/${workflow.id}`);
  };

  const handleBuilderClick = async () => {
    router.push(`/workflows/builder/${workflow.id}`);
  };

  const triggerTypes = workflow.triggers.map((trigger) => trigger.type);

  const lastExecutions = workflow?.last_executions?.slice(0, 15) || [];
  const lastProviderConfigRequiredExec = lastExecutions.filter(
    (execution) => execution?.status === "providers_not_configured"
  );
  const isAllExecutionProvidersConfigured =
    lastProviderConfigRequiredExec.length === lastExecutions.length;

  const customFormatter: Formatter = (
    value: number,
    unit: Unit,
    suffix: Suffix
  ) => {
    if (!workflow.last_execution_started && isAllExecutionProvidersConfigured) {
      return "";
    }

    const formattedString = formatDistanceToNowStrict(
      new Date(workflow.last_execution_started + "Z"),
      { addSuffix: true }
    );

    return formattedString
      .replace("about ", "")
      .replace("minute", "min")
      .replace("second", "sec")
      .replace("hour", "hr");
  };

  const isManualTriggerPresent = workflow?.triggers?.find(
    (t) => t.type === "manual"
  );

  return (
    <div>
      {isRunning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <KeepLoader />
        </div>
      )}
      <Card
        className="relative flex flex-col justify-between p-4 h-full border-2 border-transparent hover:border-orange-400 overflow-hidden cursor-pointer"
        onClick={handleWorkflowClick}
      >
        <div className="absolute top-0 right-0 mt-2 mr-2 mb-2 flex items-center flex-wrap">
          {workflow.provisioned && (
            <Badge color="orange" size="xs" className="mr-2 mb-2">
              Provisioned
            </Badge>
          )}
          {workflow.alertRule && (
            <Badge color="orange" size="xs" className="mr-2 mb-2">
              Alert Rule
            </Badge>
          )}
          {workflow.disabled && (
            <Badge color="slate" size="xs" className="mr-2 mb-2">
              Disabled
            </Badge>
          )}
          {!!handleRunClick && (
            <WorkflowMenu
              onDelete={handleDeleteClick}
              onRun={handleRunClick}
              onDownload={handleDownloadClick}
              onView={handleViewClick}
              onBuilder={handleBuilderClick}
              onToggleState={toggleWorkflow}
              isDisabled={workflow.disabled}
              runButtonToolTip={message}
              isRunButtonDisabled={!!isRunButtonDisabled}
              provisioned={workflow.provisioned}
            />
          )}
        </div>
        <WorkflowGraph workflow={workflow} />
        <div className="container flex flex-col space-between">
          <div className="h-24">
            <h2 className="truncate leading-6 font-bold text-base md:text-lg lg:text-xl">
              {workflow?.name || "Unkown"}
            </h2>
            <p className="text-gray-500 line-clamp-2">
              {workflow?.description || "no description"}
            </p>
          </div>
          <div className="flex justify-between items-end">
            <div className="flex flex-row items-center gap-1 flex-wrap text-sm">
              {workflow.triggers.map((trigger) => (
                <WorkflowTriggerBadge
                  key={trigger.type}
                  trigger={trigger}
                  onClick={(e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    setOpenTriggerModal(true);
                  }}
                />
              ))}
            </div>
            {!isAllExecutionProvidersConfigured &&
              workflow?.last_execution_started && (
                <div className="text-gray-500 text-sm text-right cursor-pointer truncate max-w-full mt-2 grow min-w-[max-content]">
                  <TimeAgo
                    date={workflow?.last_execution_started + "Z"}
                    formatter={customFormatter}
                  />
                </div>
              )}
          </div>
        </div>
      </Card>

      {!!getTriggerModalProps && (
        <AlertTriggerModal {...getTriggerModalProps()} />
      )}
      <Modal
        isOpen={openTriggerModal}
        onClose={() => {
          setOpenTriggerModal(false);
        }}
      >
        <Title>Triggers</Title>
        <div>
          {workflow.triggers.length > 0 ? (
            <List>
              {workflow.triggers.map((trigger, index) => (
                <TriggerTile key={index} trigger={trigger} />
              ))}
            </List>
          ) : (
            <p className="text-xs text-center mx-4 mt-5 text-tremor-content dark:text-dark-tremor-content">
              This workflow does not have any triggers.
            </p>
          )}
        </div>
        <div className="mt-2.5">
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            onClick={() => setOpenTriggerModal(false)}
          >
            Close
          </Button>
        </div>
      </Modal>
    </div>
  );
}

export default WorkflowTile;
