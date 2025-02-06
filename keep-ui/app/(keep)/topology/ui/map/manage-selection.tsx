"use client";

import { Edge, useOnSelectionChange } from "@xyflow/react";
import { useState, useCallback, useContext, useEffect } from "react";
import { cn } from "@/utils/helpers";
import { Button } from "@/components/ui";
import {
  useTopologyApplications,
  TopologyApplication,
  ServiceNodeType,
  TopologyNode,
} from "@/app/(keep)/topology/model";
import { TopologySearchContext } from "../../TopologySearchContext";
import { ApplicationModal } from "@/app/(keep)/topology/ui/applications/application-modal";
import { showErrorToast } from "@/shared/ui";
import {
  TopologyService,
  TopologyServiceWithMutator,
} from "../../model/models";
import {
  AddEditNodeSidePanel,
  TopologyServiceFormProps,
} from "./AddEditNodeSidePanel";
import { useApi } from "@/shared/lib/hooks/useApi";
import { toast } from "react-toastify";
import { KeyedMutator } from "swr";

export function ManageSelection({
  className,
  topologyMutator,
  getServiceById,
}: {
  className?: string;
  topologyMutator: KeyedMutator<TopologyService[]>;
  getServiceById: (_id: string) => TopologyService | undefined;
}) {
  const { setSelectedObjectId } = useContext(TopologySearchContext);
  const { applications, addApplication, removeApplication, updateApplication } =
    useTopologyApplications();
  const [selectedApplication, setSelectedApplication] =
    useState<TopologyApplication | null>(null);
  const [selectedServices, setSelectedServices] = useState<
    TopologyServiceWithMutator[]
  >([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSidePanelOpen, setIsSidePanelOpen] = useState<boolean>(false);
  const [serviceToEdit, setServiceToEdit] = useState<
    TopologyServiceWithMutator | undefined
  >(undefined);
  const api = useApi();
  const handleServicesDelete = async () => {
    try {
      const response = await api.delete("/topology/services", {
        service_ids: selectedServices.map((service) => service.id),
      });
      selectedServices[0].topologyMutator();
    } catch (error) {
      toast.error(
        `Error while deleting ${selectedServices.length === 1 ? "service" : "services"}: ${error}`
      );
    }
  };
  const [isDependencyEditable, setIsDependencyEditable] =
    useState<boolean>(false);

  const [selectedEdges, setSelectedEdges] = useState<Edge[]>([]);

  useEffect(() => {
    if (
      selectedEdges.length === 1 &&
      getServiceById(selectedEdges[0].source)?.is_manual === true &&
      getServiceById(selectedEdges[0].target)?.is_manual === true
    ) {
      setIsDependencyEditable(true);
    } else {
      setIsDependencyEditable(false);
    }
  }, [selectedEdges, getServiceById]);

  const updateSelectedServicesAndEdges = useCallback(
    ({ nodes, edges }: { nodes: TopologyNode[]; edges: Edge[] }) => {
      if (isModalOpen) {
        // Avoid dropping selection when focus is on the modal
        return;
      }
      setSelectedEdges(edges.map((edge) => ({ ...edge })));
      if (edges.length > 0) {
        return;
      }
      if (nodes.length === 0) {
        setSelectedServices([]);
        setSelectedApplication(null);
        return;
      }
      const servicesNodes = nodes.filter((node) => node.type === "service");
      setSelectedServices(
        servicesNodes.map(
          (node: TopologyNode) =>
            ({ ...node.data }) as TopologyServiceWithMutator
        )
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
    onChange: updateSelectedServicesAndEdges,
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

  const editEdgeProtocol = async (edge: Edge) => {
    const protocol = prompt(
      "Please enter the protocol:",
      edge.label?.toString()
    );
    if (protocol !== null) {
      try {
        const response = await api.put("/topology/dependency", {
          id: edge.id,
          protocol: protocol,
        });
        topologyMutator();
      } catch (error) {
        toast.error("Failed to update protocol");
      }
    }
  };

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

  const renderCreateApplicationAndManageServicesForm = () => {
    return (
      <>
        <p>
          {selectedServices.length > 0 &&
            `Selected: ${selectedServices
              .map((service) => service.display_name)
              .join(", ")}`}
        </p>
        <div className="">
          {selectedServices.length === 1 && selectedServices[0].is_manual && (
            <Button
              color="orange"
              size="xs"
              variant="secondary"
              className="mr-3"
              onClick={() => {
                setIsSidePanelOpen(true);
                setServiceToEdit(selectedServices[0]);
              }}
            >
              Update Service
            </Button>
          )}
          {selectedServices.length > 0 &&
            selectedServices.every((service) => service.is_manual === true) && (
              <Button
                color="red"
                size="xs"
                variant="primary"
                className="mr-3"
                onClick={() => handleServicesDelete()}
              >
                Delete {selectedServices.length === 1 ? "Service" : "Services"}
              </Button>
            )}
          <Button
            color="orange"
            size="xs"
            variant="primary"
            onClick={() => setIsModalOpen(true)}
          >
            Create Application
          </Button>
        </div>
        {serviceToEdit && (
          <AddEditNodeSidePanel
            isOpen={isSidePanelOpen}
            editData={
              {
                ...serviceToEdit,
                tags: serviceToEdit.tags?.join(","),
              } as TopologyServiceFormProps
            }
            topologyMutator={serviceToEdit.topologyMutator}
            handleClose={() => {
              setIsSidePanelOpen(false);
              setServiceToEdit(undefined);
            }}
          />
        )}
        <ApplicationModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          actionType="create"
          application={{
            services: selectedServices.map(
              (node: TopologyServiceWithMutator) => ({
                id: node.id,
                name: node.display_name as string,
                service: node.service,
              })
            ),
          }}
          onSubmit={createApplication}
        />
      </>
    );
  };

  const renderEditEdgeToolBar = () => {
    return (
      <>
        <div></div>
        <div className="flex gap-2">
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            onClick={() => editEdgeProtocol(selectedEdges[0])}
          >
            Edit Dependency
          </Button>
        </div>
      </>
    );
  };

  if (
    selectedServices.length === 0 &&
    selectedApplication === null &&
    !isDependencyEditable
  ) {
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
        ? renderCreateApplicationAndManageServicesForm()
        : null}
      {isDependencyEditable ? renderEditEdgeToolBar() : null}
    </div>
  );
}
