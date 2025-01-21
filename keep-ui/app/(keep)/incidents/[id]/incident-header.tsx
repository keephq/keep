import React, { useState } from "react";
import { Title, Badge, Icon, Button } from "@tremor/react";
import { ArrowLeftIcon } from "@heroicons/react/24/outline";
import { MdPlayArrow, MdModeEdit } from "react-icons/md";
import { Link } from "@/components/ui";
import { IncidentDto } from "@/entities/incidents/model";
import { IncidentSeverityBadge } from "@/entities/incidents/ui";
import { IncidentStatusBadge } from "@/entities/incidents/ui";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import { DateTimeField } from "@/shared/ui";
import Modal from "@/components/ui/Modal";
import { CreateOrUpdateIncidentForm } from "@/features/create-or-update-incident";
import ManualRunWorkflowModal from "@/app/(keep)/workflows/manual-run-workflow-modal";
import { IncidentAssignee } from "@/entities/incidents/ui/IncidentAssignee";

export function IncidentHeader({ incident }: { incident: IncidentDto }) {
  const [isFormOpen, setIsFormOpen] = useState<boolean>(false);
  const [runWorkflowModalIncident, setRunWorkflowModalIncident] =
    useState<IncidentDto | null>(null);

  const handleRunWorkflow = () => {
    setRunWorkflowModalIncident(incident);
  };

  const handleStartEdit = () => {
    setIsFormOpen(true);
  };

  return (
    <div className="flex flex-col">
      {/* Title and Back Button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center">
          <Link
            href="/incidents"
            className="p-2 hover:bg-gray-100 rounded-full text-gray-400"
          >
            <ArrowLeftIcon className="h-6 w-6" />
          </Link>
          <Title>{getIncidentName(incident)}</Title>
        </div>

        {incident.is_confirmed && (
          <div className="flex gap-2">
            <Button
              color="orange"
              size="xs"
              variant="secondary"
              icon={MdPlayArrow}
              onClick={handleRunWorkflow}
            >
              Run Workflow
            </Button>
            <Button
              color="orange"
              size="xs"
              variant="secondary"
              icon={MdModeEdit}
              onClick={handleStartEdit}
            >
              Edit Incident
            </Button>
          </div>
        )}
      </div>

      {/* Summary */}
      <div className="text-gray-400 max-w-3xl">
        {incident.user_summary || incident.generated_summary}
      </div>

      {/* Metadata Box */}
      <div className="bg-gray-200 p-2">
        <div className="flex flex-wrap gap-4 divide-x divide-gray-300">
          <div className="flex items-center">
            <IncidentSeverityBadge severity={incident.severity} size="md" />
          </div>

          <div className="flex items-center gap-2 pl-4">
            <IncidentStatusBadge status={incident.status} size="md" />
          </div>

          <div className="flex items-center pl-4">
            <IncidentAssignee
              assignee={incident.assignee}
              incidentId={incident.id}
            />
          </div>

          <div className="flex items-center pl-4">
            <span className="text-gray-400 mr-4">Started</span>
            <DateTimeField
              date={incident.start_time}
              showRelative={false}
              className="text-gray-900"
            />
          </div>

          <div className="flex items-center pl-4">
            <span className="text-gray-400 mr-4">Last seen</span>
            <DateTimeField
              date={incident.last_seen_time}
              showRelative={false}
              className="text-gray-900"
            />
          </div>
        </div>
      </div>

      <Modal
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        className="w-[600px]"
        title="Edit Incident"
      >
        <CreateOrUpdateIncidentForm
          incidentToEdit={incident}
          exitCallback={() => setIsFormOpen(false)}
        />
      </Modal>

      <ManualRunWorkflowModal
        incident={runWorkflowModalIncident}
        handleClose={() => setRunWorkflowModalIncident(null)}
      />
    </div>
  );
}

export default IncidentHeader;
