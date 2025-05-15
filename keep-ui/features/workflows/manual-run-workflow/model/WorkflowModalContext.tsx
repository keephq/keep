"use client";

import { createContext, useContext, useState } from "react";
import clsx from "clsx";
import { Workflow } from "@/shared/api/workflows";
import { WorkflowUnsavedChangesForm } from "../ui/WorkflowUnsavedChangesForm";
import Modal from "@/components/ui/Modal";
import { WorkflowAlertIncidentDependenciesForm } from "@/entities/workflows/ui/WorkflowAlertIncidentDependenciesForm";
import { WorkflowInputsForm } from "../ui/WorkflowInputsForm";
import { WorkflowInput } from "@/entities/workflows/model/yaml.types";
import { AlertWorkflowRunPayload, IncidentWorkflowRunPayload } from "./types";

type InputsModalProps = {
  inputs: WorkflowInput[];
  onSubmit: (inputs: Record<string, any>) => void;
};

type AlertDependenciesModalProps = {
  workflow: Workflow;
  staticFields: any[];
  dependencies: string[];
  onSubmit: (payload: AlertWorkflowRunPayload) => void;
};

type IncidentDependenciesModalProps = {
  workflow: Workflow;
  staticFields: any[];
  dependencies: string[];
  onSubmit: (payload: IncidentWorkflowRunPayload) => void;
};

type UnsavedChangesModalProps = {
  onSaveYaml: () => void;
  onSaveUIBuilder: () => void;
  onRunWithoutSaving: () => void;
};

type WorkflowModalContextType = {
  openInputsModal: (props: InputsModalProps) => void;
  openAlertDependenciesModal: (props: AlertDependenciesModalProps) => void;
  openIncidentDependenciesModal: (
    props: IncidentDependenciesModalProps
  ) => void;
  openUnsavedChangesModal: (props: UnsavedChangesModalProps) => void;
  closeUnsavedChangesModal: () => void;
  closeInputsModal: () => void;
  closeAlertDependenciesModal: () => void;
  closeIncidentDependenciesModal: () => void;
};
const WorkflowModalContext = createContext<WorkflowModalContextType | null>(
  null
);

export function WorkflowModalProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [inputsModalProps, setInputsModalProps] =
    useState<InputsModalProps | null>(null);
  const [alertModalProps, setAlertModalProps] =
    useState<AlertDependenciesModalProps | null>(null);
  const [incidentModalProps, setIncidentModalProps] =
    useState<IncidentDependenciesModalProps | null>(null);
  const [unsavedChangesModalProps, setUnsavedChangesModalProps] =
    useState<any>(null);

  const openInputsModal = (props: InputsModalProps) => {
    setInputsModalProps(props);
  };

  const openAlertDependenciesModal = (props: AlertDependenciesModalProps) => {
    setAlertModalProps(props);
  };

  const openIncidentDependenciesModal = (
    props: IncidentDependenciesModalProps
  ) => {
    setIncidentModalProps(props);
  };

  const openUnsavedChangesModal = (props: UnsavedChangesModalProps) => {
    setUnsavedChangesModalProps(props);
  };

  const closeUnsavedChangesModal = () => {
    setUnsavedChangesModalProps(null);
  };

  const closeInputsModal = () => {
    setInputsModalProps(null);
  };

  const closeAlertDependenciesModal = () => {
    setAlertModalProps(null);
  };

  const closeIncidentDependenciesModal = () => {
    setIncidentModalProps(null);
  };

  const closeAllModals = () => {
    setInputsModalProps(null);
    setAlertModalProps(null);
    setIncidentModalProps(null);
    setUnsavedChangesModalProps(null);
  };

  const isSomeModalOpen =
    inputsModalProps ||
    alertModalProps ||
    incidentModalProps ||
    unsavedChangesModalProps;

  return (
    <WorkflowModalContext.Provider
      value={{
        openInputsModal,
        openAlertDependenciesModal,
        openIncidentDependenciesModal,
        openUnsavedChangesModal,
        closeUnsavedChangesModal,
        closeInputsModal,
        closeAlertDependenciesModal,
        closeIncidentDependenciesModal,
      }}
    >
      {children}

      {isSomeModalOpen && (
        <Modal
          isOpen={true}
          className={clsx(
            alertModalProps || incidentModalProps ? "max-w-5xl" : ""
          )}
          onClose={closeAllModals}
          title="Run Workflow"
        >
          {unsavedChangesModalProps && (
            <WorkflowUnsavedChangesForm
              {...unsavedChangesModalProps}
              onClose={closeUnsavedChangesModal}
            />
          )}
          {inputsModalProps && (
            <WorkflowInputsForm
              workflowInputs={inputsModalProps.inputs}
              onSubmit={inputsModalProps.onSubmit}
              onCancel={closeInputsModal}
            />
          )}

          {alertModalProps && (
            <WorkflowAlertIncidentDependenciesForm
              type="alert"
              {...alertModalProps}
              onCancel={closeAlertDependenciesModal}
            />
          )}

          {incidentModalProps && (
            <WorkflowAlertIncidentDependenciesForm
              type="incident"
              {...incidentModalProps}
              onCancel={closeIncidentDependenciesModal}
            />
          )}
        </Modal>
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
