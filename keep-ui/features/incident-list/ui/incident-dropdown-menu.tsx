import { PencilIcon, PlayIcon, TrashIcon } from "@heroicons/react/24/outline";
import { EllipsisHorizontalIcon } from "@heroicons/react/20/solid";
import { DropdownMenu } from "@/shared/ui";
import { IncidentDto } from "@/entities/incidents/model";
import { useIncidentActions } from "@/entities/incidents/model/useIncidentActions";

interface Props {
  incident: IncidentDto;
  handleEdit: (incident: IncidentDto) => void;
  handleRunWorkflow: (incident: IncidentDto) => void;
}

export function IncidentDropdownMenu({
  incident,
  handleEdit,
  handleRunWorkflow,
}: Props) {
  const { deleteIncident } = useIncidentActions();

  return (
    <>
      <DropdownMenu.Menu icon={EllipsisHorizontalIcon} label="">
        <DropdownMenu.Item
          icon={PencilIcon}
          label="Edit"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            handleEdit(incident);
          }}
        />
        <DropdownMenu.Item
          icon={PlayIcon}
          label="Run workflow"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            handleRunWorkflow(incident);
          }}
        />
        <DropdownMenu.Item
          icon={TrashIcon}
          label="Delete"
          variant="destructive"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            deleteIncident(incident.id);
          }}
        />
      </DropdownMenu.Menu>
    </>
  );
}
