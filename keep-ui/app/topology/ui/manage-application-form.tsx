"use client";

import { OnSelectionChangeParams, useOnSelectionChange } from "@xyflow/react";
import { useState, useCallback } from "react";
import { cn } from "utils/helpers";
import { Application } from "../models";
import Button from "@/components/ui/Button";
import Modal from "@/components/ui/Modal";
import { CreateOrUpdateApplicationForm } from "./create-or-update-application";
import { useApplications } from "../../../utils/hooks/useApplications";

export function ManageApplicationForm({
  zoomToNode,
  className,
}: {
  zoomToNode: (nodeId: string) => void;
  className?: string;
}) {
  const { applications, removeApplication, updateApplication } =
    useApplications();
  const [selectedApplication, setSelectedApplication] =
    useState<Application | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const onChange = useCallback(
    ({ nodes }: OnSelectionChangeParams) => {
      if (nodes.length === 0) {
        setSelectedApplication(null);
        return;
      }
      const applicationNode = nodes.find((node) => node.type === "application");
      if (!applicationNode) {
        return;
      }
      const applicationId = applicationNode.id;
      const applicationInLocalStorage = applications.find(
        (application) => application.name === applicationId
      );
      if (!applicationInLocalStorage) {
        return;
      }
      setSelectedApplication(applicationInLocalStorage);
    },
    [JSON.stringify(applications)]
  );

  useOnSelectionChange({
    onChange,
  });

  const deleteApplication = (applicationId: string) => {
    const firstService = selectedApplication?.services[0];
    removeApplication(applicationId);
    setSelectedApplication(null);
    if (!firstService) {
      return;
    }
    setTimeout(() => {
      zoomToNode(firstService.name);
    }, 100);
  };

  const handleUpdateApplication = (updatedApplication: Application) => {
    updateApplication(updatedApplication);
    setTimeout(() => {
      zoomToNode(updatedApplication.name);
    }, 100);
  };

  if (selectedApplication === null) {
    return null;
  }

  return (
    <div
      className={cn(
        "flex justify-between items-center gap-2 bg-white border-b border-gray-200 px-4 py-2 text-sm",
        className
      )}
    >
      <p className="text-lg font-bold">{selectedApplication.name}</p>
      <div className="flex gap-2">
        <Button
          color="orange"
          size="xs"
          variant="secondary"
          onClick={() => setIsModalOpen(true)}
        >
          Edit
        </Button>
        <Button
          color="red"
          size="xs"
          variant="destructive"
          onClick={() => deleteApplication(selectedApplication.id)}
        >
          Delete application
        </Button>
      </div>
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Edit application"
      >
        <CreateOrUpdateApplicationForm
          action="edit"
          application={selectedApplication}
          onSubmit={handleUpdateApplication}
          onCancel={() => setIsModalOpen(false)}
        />
      </Modal>
    </div>
  );
}
