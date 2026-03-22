import { Button, Title, Subtitle } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { useIncidentActions } from "@/entities/incidents/model";
import { useMemo, useState } from "react";
import { Select, VerticalRoundedList } from "@/shared/ui";
import { IncidentIconName } from "@/entities/incidents/ui";
import { useI18n } from "@/i18n/hooks/useI18n";
import {
  useIncident,
  useIncidents,
  usePollIncidents,
} from "@/utils/hooks/useIncidents";
import Skeleton from "react-loading-skeleton";

interface Props {
  sourceIncidentId: string;
  alertFingerprints: string[];
  handleClose: () => void;
  onSuccess?: () => void;
}

export function SplitIncidentAlertsModal({
  sourceIncidentId,
  handleClose,
  onSuccess,
  alertFingerprints,
}: Props) {
  const { data: sourceIncident, isLoading: isSourceIncidentLoading } =
    useIncident(sourceIncidentId);
  const {
    data: incidents,
    isLoading,
    mutate,
    error,
  } = useIncidents({ candidate: false, predicted: null, limit: 100 });
  usePollIncidents(mutate);

  const [destinationIncidentId, setDestinationIncidentId] = useState<string>();
  const destinationIncident = incidents?.items.find(
    (incident) => incident.id === destinationIncidentId
  );

  const incidentOptions = useMemo(() => {
    if (!incidents) {
      return [];
    }
    return incidents.items
      .filter((incident) => incident.id !== sourceIncidentId)
      .map((incident) => ({
        value: incident.id,
        label: <IncidentIconName inline incident={incident} />,
      }));
  }, [sourceIncidentId, incidents]);

  const selectValue = useMemo(() => {
    if (!destinationIncident) {
      return null;
    }
    return {
      value: destinationIncidentId,
      label: <IncidentIconName inline incident={destinationIncident} />,
    };
  }, [destinationIncidentId, destinationIncident]);

  const { splitIncidentAlerts } = useIncidentActions();
  const { t } = useI18n();
  const handleSplit = () => {
    splitIncidentAlerts(
      sourceIncidentId,
      alertFingerprints,
      destinationIncidentId!
    );
    handleClose();
    onSuccess?.();
  };

  return (
    <Modal onClose={handleClose} isOpen={true}>
      <div className="flex flex-col gap-5">
        <div>
          <Title>{t("incidents.split.title")}</Title>
          <Subtitle>
            {t("incidents.split.description")}
          </Subtitle>
        </div>
        <div>
          <div className="mb-1">
            <span className="font-bold">{t("incidents.split.sourceIncident")}</span>
          </div>
          <VerticalRoundedList>
            {isSourceIncidentLoading || !sourceIncident ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <IncidentIconName incident={sourceIncident} />
            )}
          </VerticalRoundedList>
        </div>
        <div>
          <div className="mb-1">
            <span className="font-bold">{t("incidents.split.destinationIncident")}</span>
          </div>
          <Select
            instanceId="split-incident-alerts-destination-incident-select"
            options={incidentOptions}
            value={selectValue}
            onChange={(option) =>
              option && setDestinationIncidentId(option.value)
            }
            placeholder={t("incidents.split.selectDestination")}
          />
        </div>
      </div>
      <div className="flex justify-end mt-4 gap-2">
        <Button onClick={handleClose} color="orange" variant="secondary">
          {t("common.actions.cancel")}
        </Button>
        <Button onClick={handleSplit} color="orange">
          {t("incidents.split.confirmSplit")}
        </Button>
      </div>
    </Modal>
  );
}
