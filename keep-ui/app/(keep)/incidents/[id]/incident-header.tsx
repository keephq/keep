"use client";

import {
  useIncidentActions,
  type IncidentDto,
} from "@/entities/incidents/model";
import { Button, Icon, Subtitle, Title } from "@tremor/react";
import { Link } from "@/components/ui";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import { MdBlock, MdDone, MdModeEdit, MdPlayArrow } from "react-icons/md";
import React, { useState } from "react";
import { useRouter } from "next/navigation";
import ManualRunWorkflowModal from "@/app/(keep)/workflows/manual-run-workflow-modal";
import { CreateOrUpdateIncidentForm } from "@/features/create-or-update-incident";
import Modal from "@/components/ui/Modal";
import { IncidentSeverityBadge } from "@/entities/incidents/ui";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import { useIncident } from "@/utils/hooks/useIncidents";
import { IncidentOverview } from "./incident-overview";
import { CopilotKit } from "@copilotkit/react-core";

export function IncidentHeader({
  incident: initialIncidentData,
}: {
  incident: IncidentDto;
}) {
  const { data: fetchedIncident } = useIncident(initialIncidentData.id, {
    fallbackData: initialIncidentData,
    revalidateOnMount: false,
  });
  const { deleteIncident, confirmPredictedIncident } = useIncidentActions();
  const incident = fetchedIncident || initialIncidentData;

  const router = useRouter();

  const [isFormOpen, setIsFormOpen] = useState<boolean>(false);

  const [runWorkflowModalIncident, setRunWorkflowModalIncident] =
    useState<IncidentDto | null>();

  const handleCloseForm = () => {
    setIsFormOpen(false);
  };

  const handleFinishEdit = () => {
    setIsFormOpen(false);
  };
  const handleRunWorkflow = () => {
    setRunWorkflowModalIncident(incident);
  };

  const handleStartEdit = () => {
    setIsFormOpen(true);
  };

  return (
    <CopilotKit runtimeUrl="/api/copilotkit">
      <header className="flex flex-col gap-4">
        <Subtitle className="text-sm">
          <Link href="/incidents">All Incidents</Link>{" "}
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          {incident.is_confirmed ? "⚔️ " : "Possible "}Incident Details
        </Subtitle>
        <div className="flex justify-between items-end text-sm gap-2">
          <Title className="prose-2xl flex-grow flex flex-col gap-1">
            <IncidentSeverityBadge severity={incident.severity} />
            <span>{getIncidentName(incident)}</span>
          </Title>
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            icon={MdPlayArrow}
            onClick={(e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              handleRunWorkflow();
            }}
          >
            Run Workflow
          </Button>
          {incident.is_confirmed && (
            <Button
              color="orange"
              size="xs"
              variant="secondary"
              icon={MdModeEdit}
              onClick={(e: React.MouseEvent) => {
                e.preventDefault();
                e.stopPropagation();
                handleStartEdit();
              }}
            >
              Edit Incident
            </Button>
          )}
          {!incident.is_confirmed && (
            <div className="space-x-1 flex flex-row items-center justify-center">
              <Button
                color="orange"
                size="xs"
                tooltip="Confirm incident"
                variant="secondary"
                title="Confirm"
                icon={MdDone}
                onClick={(e: React.MouseEvent) => {
                  e.preventDefault();
                  e.stopPropagation();
                  confirmPredictedIncident(incident.id!);
                }}
              >
                Confirm
              </Button>
              <Button
                color="red"
                size="xs"
                variant="secondary"
                tooltip={"Discard"}
                icon={MdBlock}
                onClick={async (e: React.MouseEvent) => {
                  e.preventDefault();
                  e.stopPropagation();
                  const success = await deleteIncident(incident.id);
                  if (success) {
                    router.push("/incidents");
                  }
                }}
              />
            </div>
          )}
        </div>
      </header>
      <IncidentOverview incident={incident} />
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        className="w-[600px]"
        title="Edit Incident"
      >
        <CreateOrUpdateIncidentForm
          incidentToEdit={incident}
          exitCallback={handleFinishEdit}
        />
      </Modal>
      <ManualRunWorkflowModal
        incident={runWorkflowModalIncident}
        handleClose={() => setRunWorkflowModalIncident(null)}
      />
    </CopilotKit>
  );
}
