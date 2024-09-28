"use client";

import { TopologyApplication } from "../../models";
import { ApplicationCard } from "./application-card";
import Button from "@/components/ui/Button";
import Modal from "@/components/ui/Modal";
import { CreateOrUpdateApplicationForm } from "./create-or-update-application-form";
import { toast } from "react-toastify";
import { useCallback, useContext, useState } from "react";
import { useTopologyApplications } from "../../../../utils/hooks/useApplications";
import { Card, Subtitle, Title } from "@tremor/react";
import { ServiceSearchContext } from "../../service-search-context";

export function ApplicationsList({
  applications: initialApplications,
}: {
  applications?: TopologyApplication[];
}) {
  const { applications, addApplication, removeApplication, updateApplication } =
    useTopologyApplications({
      initialData: initialApplications,
    });
  const { setSelectedServiceId } = useContext(ServiceSearchContext);
  const [selectedApplication, setSelectedApplication] =
    useState<TopologyApplication | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  const handleEditApplication = (application: TopologyApplication) => {
    setSelectedApplication(application);
    setIsEditModalOpen(true);
  };

  const handleCreateApplication = useCallback(
    async (applicationValues: Omit<TopologyApplication, "id">) => {
      const application = await addApplication(applicationValues);
      setIsCreateModalOpen(false);
    },
    [addApplication]
  );

  const handleUpdateApplication = useCallback(
    async (updatedApplication: TopologyApplication) => {
      const startTime = performance.now();
      console.log("Updating application", startTime);
      setIsEditModalOpen(false);
      updateApplication(updatedApplication).then(
        () => {
          const endTime = performance.now();
          console.log(
            "Application updated in",
            endTime - startTime,
            "ms; ",
            endTime
          );
        },
        (error) => {
          toast.error("Failed to update application");
        }
      );
    },
    [updateApplication]
  );

  const handleRemoveApplication = useCallback(
    async (applicationId: string) => {
      try {
        removeApplication(applicationId);
        setSelectedApplication(null);
        setIsEditModalOpen(false);
      } catch (error) {
        toast.error("Failed to delete application");
      }
    },
    [removeApplication]
  );

  if (!applications.length) {
    return (
      <Card className="flex flex-col gap-4 items-start">
        <div>
          <Title>No applications yet</Title>
          <Subtitle>
            Group services that work together into applications for easier
            management and monitoring
          </Subtitle>
        </div>
        <Button
          variant="primary"
          color="orange"
          onClick={() => setIsCreateModalOpen(true)}
        >
          Create Application
        </Button>
      </Card>
    );
  }

  return (
    <>
      <div className="flex w-full items-center justify-between mb-4">
        <div>
          <Title>Applications</Title>
          <Subtitle>
            Group services that work together into applications for easier
            management and monitoring
          </Subtitle>
        </div>
        <div>
          <Button
            variant="primary"
            color="orange"
            onClick={() => setIsCreateModalOpen(true)}
          >
            Add Application
          </Button>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {applications.map((application) => (
          <ApplicationCard
            key={application.id}
            application={application}
            actionButtons={
              <div className="flex gap-4">
                <Button
                  variant="light"
                  color="orange"
                  onClick={() => {
                    setSelectedServiceId(application.id);
                  }}
                >
                  Show on map
                </Button>
                <Button
                  variant="secondary"
                  color="orange"
                  onClick={() => handleEditApplication(application)}
                >
                  Edit
                </Button>
              </div>
            }
          />
        ))}
      </div>
      {isEditModalOpen && selectedApplication ? (
        <Modal
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          title="Edit application"
        >
          <CreateOrUpdateApplicationForm
            action="edit"
            application={selectedApplication}
            onSubmit={handleUpdateApplication}
            onCancel={() => setIsEditModalOpen(false)}
            onDelete={() => handleRemoveApplication(selectedApplication.id)}
          />
        </Modal>
      ) : null}
      {isCreateModalOpen ? (
        <Modal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          title="Create application"
        >
          <CreateOrUpdateApplicationForm
            action="create"
            onSubmit={handleCreateApplication}
            onCancel={() => setIsCreateModalOpen(false)}
          />
        </Modal>
      ) : null}
    </>
  );
}
