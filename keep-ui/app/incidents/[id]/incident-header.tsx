import { IncidentDto } from "@/app/incidents/models";
import { Badge, Button, Icon, Subtitle, Title } from "@tremor/react";
import { Link } from "@/components/ui";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import { MdBlock, MdDone, MdModeEdit, MdPlayArrow } from "react-icons/md";
import React, { useState } from "react";
import {
  deleteIncident,
  handleConfirmPredictedIncident,
} from "@/app/incidents/incident-candidate-actions";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useApiUrl } from "@/utils/hooks/useConfig";
import ManualRunWorkflowModal from "@/app/workflows/manual-run-workflow-modal";
import CreateOrUpdateIncident from "@/app/incidents/create-or-update-incident";
import Modal from "@/components/ui/Modal";
import { KeyedMutator } from "swr";

function SeverityBadge({ severity }: { severity: IncidentDto["severity"] }) {
  let severityColor;
  if (severity === "critical") {
    severityColor = "red";
  } else if (severity === "info") {
    severityColor = "blue";
  } else if (severity === "warning") {
    severityColor = "yellow";
  }
  return (
    <Badge color={severityColor} className="capitalize" size="xs">
      {severity}
    </Badge>
  );
}

export function IncidentHeader({
  incident,
  mutate,
}: {
  incident: IncidentDto;
  mutate: KeyedMutator<IncidentDto>;
}) {
  const router = useRouter();
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

  const [isFormOpen, setIsFormOpen] = useState<boolean>(false);

  const [runWorkflowModalIncident, setRunWorkflowModalIncident] =
    useState<IncidentDto | null>();

  const handleCloseForm = () => {
    setIsFormOpen(false);
  };

  const handleFinishEdit = () => {
    setIsFormOpen(false);
    mutate();
  };
  const handleRunWorkflow = () => {
    setRunWorkflowModalIncident(incident);
    mutate();
  };

  const handleStartEdit = () => {
    setIsFormOpen(true);
  };

  return (
    <>
      <header className="flex flex-col gap-4">
        <Subtitle className="text-sm">
          <Link href="/incidents">All Incidents</Link>{" "}
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          {incident.is_confirmed ? "⚔️ " : "Possible "}Incident Details
        </Subtitle>
        <div className="flex justify-between items-end text-sm gap-1">
          <Title className="prose-2xl flex-grow flex flex-col gap-1">
            <SeverityBadge severity={incident.severity} />
            <span>
              {incident.user_generated_name || incident.ai_generated_name}
            </span>
          </Title>
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            icon={MdPlayArrow}
            tooltip="Run Workflow"
            onClick={(e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              handleRunWorkflow();
            }}
          />
          {incident.is_confirmed && (
            <Button
              color="orange"
              size="xs"
              variant="secondary"
              icon={MdModeEdit}
              tooltip="Edit Incident"
              onClick={(e: React.MouseEvent) => {
                e.preventDefault();
                e.stopPropagation();
                handleStartEdit();
              }}
            />
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
                  handleConfirmPredictedIncident({
                    apiUrl: apiUrl!,
                    incidentId: incident.id!,
                    mutate,
                    session,
                  });
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
                  const success = await deleteIncident({
                    apiUrl: apiUrl!,
                    incidentId: incident.id!,
                    mutate,
                    session,
                  });
                  if (success) {
                    router.push("/incidents");
                  }
                }}
              />
            </div>
          )}
        </div>
      </header>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        className="w-[600px]"
        title="Edit Incident"
      >
        <CreateOrUpdateIncident
          incidentToEdit={incident}
          exitCallback={handleFinishEdit}
        />
      </Modal>
      <ManualRunWorkflowModal
        incident={runWorkflowModalIncident}
        handleClose={() => setRunWorkflowModalIncident(null)}
      />
    </>
  );
}
