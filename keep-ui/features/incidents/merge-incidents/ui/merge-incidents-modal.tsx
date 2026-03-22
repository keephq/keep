import { Button, Title, Subtitle } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import type { IncidentDto } from "@/entities/incidents/model";
import { useIncidentActions, Status } from "@/entities/incidents/model";
import { useMemo, useState } from "react";
import { Select, VerticalRoundedList } from "@/shared/ui";
import { IncidentIconName } from "@/entities/incidents/ui";
import { useI18n } from "@/i18n/hooks/useI18n";

interface Props {
  incidents: IncidentDto[];
  handleClose: () => void;
  onSuccess?: () => void;
}

export function MergeIncidentsModal({
  incidents,
  handleClose,
  onSuccess,
}: Props) {
  const [destinationIncidentId, setDestinationIncidentId] = useState<string>(
    incidents[0].id
  );
  const destinationIncident = incidents.find(
    (incident) => incident.id === destinationIncidentId
  );
  const sourceIncidents = incidents.filter(
    (incident) => incident.id !== destinationIncidentId
  );

  const incidentOptions = useMemo(() => {
    return incidents.map((incident) => ({
      value: incident.id,
      label: <IncidentIconName inline incident={incident} />,
    }));
  }, [incidents]);

  const selectValue = useMemo(() => {
    return {
      value: destinationIncidentId,
      label: <IncidentIconName inline incident={destinationIncident!} />,
    };
  }, [destinationIncidentId, destinationIncident]);

  const errors = useMemo(() => {
    const errorDict: Record<string, boolean> = {};
    if (sourceIncidents.every((i) => i.status === Status.Merged)) {
      errorDict["alreadyMerged"] = true;
    }
    return errorDict;
  }, [sourceIncidents]);

  const { mergeIncidents } = useIncidentActions();
  const { t } = useI18n();
  const handleMerge = () => {
    mergeIncidents(sourceIncidents, destinationIncident!);
    handleClose();
    onSuccess?.();
  };

  return (
    <Modal onClose={handleClose} isOpen={true}>
      <div className="flex flex-col gap-5">
        <div>
          <Title>{t("incidents.merge.title")}</Title>
          <Subtitle>
            {t("incidents.merge.description")}{" "}
            <b>{t("incidents.merge.merged")}</b>
          </Subtitle>
        </div>
        <div>
          <div className="mb-1">
            <span className="font-bold">{t("incidents.merge.sourceIncidents")}</span>
            {errors.alreadyMerged && (
              <p className="text-red-500 text-sm mt-1">
                {t("incidents.merge.alreadyMerged")}
              </p>
            )}
          </div>
          <VerticalRoundedList>
            {sourceIncidents.map((incident) => (
              <IncidentIconName key={incident.id} incident={incident} />
            ))}
          </VerticalRoundedList>
        </div>
        <div>
          <div className="mb-1">
            <span className="font-bold">{t("incidents.merge.destinationIncident")}</span>
          </div>
          <Select
            instanceId="merge-incidents-destination-incident-select"
            options={incidentOptions}
            value={selectValue}
            onChange={(option) => setDestinationIncidentId(option!.value)}
            placeholder={t("incidents.merge.selectDestination")}
          />
        </div>
      </div>
      <div className="flex justify-end mt-4 gap-2">
        <Button onClick={handleClose} color="orange" variant="secondary">
          {t("common.actions.cancel")}
        </Button>
        <Button
          onClick={handleMerge}
          color="orange"
          disabled={Object.values(errors).length != 0}
        >
          {t("incidents.merge.confirmMerge")}
        </Button>
      </div>
    </Modal>
  );
}
