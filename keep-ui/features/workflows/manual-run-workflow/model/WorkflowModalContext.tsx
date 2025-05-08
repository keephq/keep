"use client";

import { createContext, useContext, useState } from "react";
import { Workflow } from "@/shared/api/workflows";
import { IncidentDto } from "@/entities/incidents/model";
import { AlertDto } from "@/entities/alerts/model";
import { ManualRunWorkflowModal } from "../ui/manual-run-workflow-modal";
import { AlertTriggerModal } from "../ui/workflow-run-with-alert-modal";
import { IncidentDependenciesModal } from "../ui/IncidentDependenciesModal";
import { WorkflowUnsavedChangesModal } from "../ui/WorkflowUnsavedChangesModal";

type WorkflowModalContextType = {
  openManualInputModal: (props: {
    workflow: Workflow;
    alert?: AlertDto;
    incident?: IncidentDto;
    onSubmit: ({ inputs }: { inputs: Record<string, any> }) => void;
  }) => void;
  openAlertDependenciesModal: (props: {
    workflow: Workflow;
    staticFields: any[];
    dependencies: string[];
    onSubmit: (payload: any) => void;
  }) => void;
  openIncidentDependenciesModal: (props: {
    workflow: Workflow;
    staticFields: any[];
    dependencies: string[];
    onSubmit: (payload: any) => void;
  }) => void;
  openUnsavedChangesModal: (props: {
    onSaveYaml: () => void;
    onSaveUIBuilder: () => void;
    onRunWithoutSaving: () => void;
  }) => void;
};
const WorkflowModalContext = createContext<WorkflowModalContextType | null>(
  null
);

export function WorkflowModalProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [manualModalProps, setManualModalProps] = useState<any>(null);
  const [alertModalProps, setAlertModalProps] = useState<any>(null);
  const [incidentModalProps, setIncidentModalProps] = useState<any>(null);
  const [unsavedChangesModalProps, setUnsavedChangesModalProps] =
    useState<any>(null);

  const openManualInputModal = (props: {
    workflow: Workflow;
    alert?: AlertDto;
    incident?: IncidentDto;
    onSubmit: ({ inputs }: { inputs: Record<string, any> }) => void;
  }) => {
    setManualModalProps(props);
  };

  const openAlertDependenciesModal = (props: {
    workflow: Workflow;
    staticFields: any[];
    dependencies: string[];
    onSubmit: (payload: any) => void;
  }) => {
    setAlertModalProps(props);
  };

  const openIncidentDependenciesModal = (props: {
    workflow: Workflow;
    staticFields: any[];
    dependencies: string[];
    onSubmit: (payload: any) => void;
  }) => {
    setIncidentModalProps(props);
  };

  const openUnsavedChangesModal = (props: {
    onSaveYaml: () => void;
    onSaveUIBuilder: () => void;
    onRunWithoutSaving: () => void;
  }) => {
    setUnsavedChangesModalProps(props);
  };

  return (
    <WorkflowModalContext.Provider
      value={{
        openManualInputModal,
        openAlertDependenciesModal,
        openIncidentDependenciesModal,
        openUnsavedChangesModal,
      }}
    >
      {children}

      {/* Render modals here, just once */}
      {manualModalProps && (
        <ManualRunWorkflowModal
          {...manualModalProps}
          isOpen={true}
          onClose={() => setManualModalProps(null)}
        />
      )}

      {alertModalProps && (
        <AlertTriggerModal
          {...alertModalProps}
          isOpen={true}
          onClose={() => setAlertModalProps(null)}
        />
      )}

      {incidentModalProps && (
        <IncidentDependenciesModal
          {...incidentModalProps}
          isOpen={true}
          onClose={() => setIncidentModalProps(null)}
        />
      )}

      {unsavedChangesModalProps && (
        <WorkflowUnsavedChangesModal
          {...unsavedChangesModalProps}
          isOpen={true}
          onClose={() => setUnsavedChangesModalProps(null)}
        />
      )}
    </WorkflowModalContext.Provider>
  );
}

export const useWorkflowModals = () => {
  const context = useContext(WorkflowModalContext);
  if (!context) {
    throw new Error(
      "useWorkflowModals must be used within a WorkflowModalProvider"
    );
  }
  return context;
};
