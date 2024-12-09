"use client";

import { useOnSelectionChange } from "@xyflow/react";
import { useState, useCallback, useContext } from "react";
import { cn } from "@/utils/helpers";
import { Button } from "@/components/ui";
import {
  useTopologyApplications,
  TopologyApplication,
  ServiceNodeType,
  TopologyServiceMinimal,
  TopologyNode,
} from "@/app/(keep)/topology/model";
import { TopologySearchContext } from "../../TopologySearchContext";
import { ApplicationModal } from "@/app/(keep)/topology/ui/applications/application-modal";
import { showErrorToast } from "@/shared/ui/utils/showErrorToast";

export function ManageSelection({ className }: { className?: string }) {
  const { setSelectedObjectId } = useContext(TopologySearchContext);
  const { applications, addApplication, removeApplication, updateApplication } =
    useTopologyApplications();
  const [selectedApplication, setSelectedApplication] =
    useState<TopologyApplication | null>(null);
  const [selectedServices, setSelectedServices] = useState<
    TopologyServiceMinimal[]
  >([]);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const updateSelectedServices = useCallback(
    ({ nodes }: { nodes: TopologyNode[] }) => {
      if (isModalOpen) {
        // Avoid dropping selection when focus is on the modal
        return;
      }
      if (nodes.length === 0) {
        setSelectedServices([]);
        setSelectedApplication(null);
        return;
      }
      const servicesNodes = nodes.filter((node) => node.type === "service");
      setSelectedServices(
        servicesNodes.map((node: TopologyNode) => ({
          id: (node as ServiceNodeType).data.id,
          name: (node as ServiceNodeType).data.display_name as string,
          service: (node as ServiceNodeType).data.service,
        }))
      );
      // Setting selected application if all services selected has the same app id in data.application_ids
      const appIds = new Set(
        servicesNodes.flatMap(
          (node: TopologyNode) => (node as ServiceNodeType).data.application_ids
        )
      );
      if (appIds.size === 1) {
        const app = applications.find(
          (app) => app.id === Array.from(appIds)[0]
        );
        if (app && app.services.length === servicesNodes.length) {
          setSelectedApplication(app);
          return;
        }
      } else {
        setSelectedApplication(null);
      }
    },
    [applications, isModalOpen]
  );

  useOnSelectionChange({
    onChange: updateSelectedServices,
  });

  const handleUpdateApplication = async (
    updatedApplication: TopologyApplication
  ) => {
    const startTime = performance.now();
    setIsModalOpen(false);
    updateApplication(updatedApplication).then(
      () => {
        setSelectedApplication(updatedApplication);
        setSelectedObjectId(updatedApplication.id);
      },
      (error) => {
        showErrorToast(error, "Failed to update application");
      }
    );
  };

  const createApplication = async (
    applicationValues: Omit<TopologyApplication, "id">
  ) => {
    const application = await addApplication(applicationValues);
    setIsModalOpen(false);
    setSelectedApplication(application);
    setSelectedServices([]);
    setSelectedObjectId(application.id);
  };

  const deleteApplication = useCallback(
    async (applicationId: string) => {
      try {
        removeApplication(applicationId);
        setSelectedApplication(null);
        setIsModalOpen(false);
      } catch (error) {
        showErrorToast(error, "Failed to delete application");
      }
    },
    [removeApplication]
  );

  const renderManageApplicationForm = () => {
    if (selectedApplication === null) {
      return null;
    }

    return (
      <>
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
        </div>
        <ApplicationModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          actionType="edit"
          application={selectedApplication}
          onSubmit={handleUpdateApplication}
          onDelete={() => deleteApplication(selectedApplication.id)}
        />
      </>
    );
  };

  const renderCreateApplicationForm = () => {
    return (
      <>
        <p>
          {selectedServices.length > 0 &&
            `Selected: ${selectedServices
              .map((service) => service.name)
              .join(", ")}`}
        </p>
        <Button
          color="orange"
          size="xs"
          variant="primary"
          onClick={() => setIsModalOpen(true)}
        >
          Create Application
        </Button>
        <ApplicationModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          actionType="create"
          application={{
            services: selectedServices,
          }}
          onSubmit={createApplication}
        />
      </>
    );
  };

  if (selectedServices.length === 0 && selectedApplication === null) {
    return null;
  }

  return (
    <div
      className={cn(
        "flex justify-between items-center gap-2 bg-white border-b border-gray-200 px-4 py-2 text-sm absolute top-0 left-0 w-full z-[25]",
        className
      )}
    >
      {selectedApplication !== null ? renderManageApplicationForm() : null}
      {selectedApplication === null && selectedServices.length > 0
        ? renderCreateApplicationForm()
        : null}
    </div>
  );
}
