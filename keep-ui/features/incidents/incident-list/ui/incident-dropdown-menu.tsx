import { PencilIcon, PlayIcon, TrashIcon } from "@heroicons/react/24/outline";
import { EllipsisHorizontalIcon } from "@heroicons/react/20/solid";
import { DropdownMenu } from "@/shared/ui";
import { IncidentDto } from "@/entities/incidents/model";
import { useIncidentActions } from "@/entities/incidents/model/useIncidentActions";
import { useI18n } from "@/i18n/hooks/useI18n";

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
  const { t } = useI18n();

  return (
    <>
      <DropdownMenu.Menu icon={EllipsisHorizontalIcon} label="">
        <DropdownMenu.Item
          icon={PencilIcon}
          label={t("incidents.dropdown.edit")}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            handleEdit(incident);
          }}
        />
        <DropdownMenu.Item
          icon={PlayIcon}
          label={t("incidents.dropdown.runWorkflow")}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            handleRunWorkflow(incident);
          }}
        />
        <DropdownMenu.Item
          icon={TrashIcon}
          label={t("incidents.dropdown.delete")}
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
