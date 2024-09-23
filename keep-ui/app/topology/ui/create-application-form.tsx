import { useState, useCallback } from "react";
import { OnSelectionChangeParams, useOnSelectionChange } from "@xyflow/react";
import { Application } from "../models";
import { Button } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { cn } from "utils/helpers";
import { CreateOrUpdateApplicationForm } from "./create-or-update-application";
import { useApplications } from "../../../utils/hooks/useApplications";

export function CreateApplicationForm({
  zoomToNode,
  className,
}: {
  zoomToNode: (nodeId: string) => void;
  className?: string;
}) {
  const { addApplication } = useApplications();
  const [selectedServices, setSelectedServices] = useState<
    {
      id: string;
      name: string;
    }[]
  >([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  // the passed handler has to be memoized, otherwise the hook will not work correctly
  const onChange = useCallback(({ nodes }: OnSelectionChangeParams) => {
    if (isModalOpen) {
      return;
    }
    setSelectedServices(
      nodes
        .filter((node) => node.type === "service")
        .map((node) => ({
          id: node.id,
          name: node.data.display_name as string,
        }))
    );
  }, []);

  useOnSelectionChange({
    onChange,
  });

  const createApplication = (applicationObj: Omit<Application, "id">) => {
    const application = addApplication(applicationObj);
    setIsModalOpen(false);
    setSelectedServices([]);
    // TODO: zoom to the newly created application when API is implemented
    // setTimeout(() => {
    //   zoomToNode(application.id);
    // }, 100);
  };

  return (
    <div
      className={cn(
        "flex justify-between items-center gap-2 bg-white border-b border-gray-200 px-4 py-2 text-sm",
        className
      )}
    >
      <p>
        {selectedServices.length > 0 &&
          `Selected: ${selectedServices.map((service) => service.name).join(", ")}`}
      </p>
      <Button
        color="orange"
        size="xs"
        variant="primary"
        onClick={() => setIsModalOpen(true)}
      >
        Create Application
      </Button>
      <Modal
        title="Create application"
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      >
        <CreateOrUpdateApplicationForm
          action="create"
          application={{
            services: selectedServices,
          }}
          onSubmit={createApplication}
          onCancel={() => setIsModalOpen(false)}
        />
      </Modal>
    </div>
  );
}
