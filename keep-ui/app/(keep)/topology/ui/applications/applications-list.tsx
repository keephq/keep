"use client";

import { ApplicationCard } from "./application-card";
import { Button } from "@/components/ui";
import { toast } from "react-toastify";
import { useCallback, useContext, useState } from "react";
import {
  useTopologyApplications,
  TopologyApplication,
} from "@/app/(keep)/topology/model";
import { Card, Subtitle, Title } from "@tremor/react";
import {
  TopologySearchContext,
  useTopologySearchContext,
} from "../../TopologySearchContext";
import { ApplicationModal } from "@/app/(keep)/topology/ui/applications/application-modal";
import { ReadOnlyAwareToaster } from "@/shared/lib/ReadOnlyAwareToaster";
import { useConfig } from "@/utils/hooks/useConfig";

type ModalState = {
  isOpen: boolean;
  actionType: "create" | "edit";
  application?: TopologyApplication;
};

const initialModalState: ModalState = {
  isOpen: false,
  actionType: "create",
  application: undefined,
};

export function ApplicationsList({
  applications: initialApplications,
}: {
  applications?: TopologyApplication[];
}) {
  const { data: configData } = useConfig();
  const { applications, addApplication, removeApplication, updateApplication } =
    useTopologyApplications({
      initialData: initialApplications,
    });
  const { setSelectedObjectId, setSelectedApplicationIds } =
    useTopologySearchContext();
  const [modalState, setModalState] = useState<ModalState>({
    isOpen: false,
    actionType: "create",
    application: undefined,
  });

  const handleEditApplication = (application: TopologyApplication) => {
    setModalState({
      isOpen: true,
      actionType: "edit",
      application,
    });
  };

  const handleCreateApplication = useCallback(
    async (applicationValues: Omit<TopologyApplication, "id">) => {
      const application = await addApplication(applicationValues);
      setModalState(initialModalState);
    },
    [addApplication]
  );

  const handleUpdateApplication = useCallback(
    async (updatedApplication: TopologyApplication) => {
      setModalState(initialModalState);
      updateApplication(updatedApplication).then(
        () => {},
        (error) => {
          ReadOnlyAwareToaster.error("Failed to update application", configData);
        }
      );
    },
    [updateApplication]
  );

  const handleRemoveApplication = useCallback(
    async (applicationId: string) => {
      try {
        removeApplication(applicationId);
        setModalState(initialModalState);
      } catch (error) {
        ReadOnlyAwareToaster.error("Failed to delete application", configData);
      }
    },
    [removeApplication]
  );

  function renderEmptyState() {
    return (
      <>
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
            onClick={() => {
              setModalState({
                isOpen: true,
                actionType: "create",
                application: undefined,
              });
            }}
          >
            Create Application
          </Button>
        </Card>
      </>
    );
  }

  return (
    <>
      {applications.length === 0 ? (
        renderEmptyState()
      ) : (
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
                onClick={() => {
                  setModalState(initialModalState);
                }}
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
                        setSelectedApplicationIds([application.id]);
                        setSelectedObjectId(application.id);
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
        </>
      )}
      {modalState.actionType === "create" ? (
        <ApplicationModal
          isOpen={modalState.isOpen}
          onClose={() => setModalState(initialModalState)}
          actionType={modalState.actionType}
          application={modalState.application}
          onSubmit={handleCreateApplication}
        />
      ) : (
        <ApplicationModal
          isOpen={modalState.isOpen}
          onClose={() => setModalState(initialModalState)}
          actionType={modalState.actionType}
          application={modalState.application!}
          onSubmit={handleUpdateApplication}
          onDelete={() => handleRemoveApplication(modalState.application!.id)}
        />
      )}
    </>
  );
}
