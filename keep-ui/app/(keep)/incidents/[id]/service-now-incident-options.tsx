"use client";

import { Button } from "@tremor/react";
import { MdLink, MdModeEdit, MdOutlineBookmarkAdd, MdOutlineOpenInNew } from "react-icons/md";
import { type IncidentDto } from "@/entities/incidents/model";

interface ServiceNowIncidentOptionsProps {
  incident: IncidentDto;
  handleRunWorkflow: () => void;
}

export function ServiceNowIncidentOptions({
  incident,
  handleRunWorkflow,
}: ServiceNowIncidentOptionsProps) {
  return (
    <>
      {incident.enrichments?.servicenow_ticket_id ? (
        <Button
          color="orange"
          size="xs"
          variant="secondary"
          className="!py-0.5 mr-2"
          icon={MdOutlineOpenInNew}
          onClick={() => {
            window.open(`https://localhost:3000/incidents/${incident.id}/servicenow`);
          }}
        >
          Open incident in ServiceNow
        </Button>
      ) : (
        <>
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            className="!py-0.5 mr-2"
            icon={MdOutlineBookmarkAdd}
            onClick={(e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              console.log(incident);
              window.open(`https://localhost:3000/?description=${incident.user_summary}&short_description=${incident.user_generated_name}`);
            }}
          >
            Create New ServiceNow Ticket
          </Button>
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            className="!py-0.5 mr-2"
            icon={MdLink}
            onClick={(e: React.MouseEvent) => {
              e.preventDefault();
              e.stopPropagation();
              handleRunWorkflow();
            }}
          >
            Link to a ServiceNow Ticket
          </Button>
        </>
      )}
    </>
  );
} 