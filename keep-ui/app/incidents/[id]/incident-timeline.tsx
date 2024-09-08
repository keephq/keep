import { useAlerts } from "utils/hooks/useAlerts";
import { IncidentDto } from "../model";
import { useIncidentAlerts } from "utils/hooks/useIncidents";
import AlertTimeline from "app/alerts/alert-timeline";

interface Props {
  incident: IncidentDto;
}
export default function IncidentTimeline({ incident }: Props) {
  const { data: alerts, isLoading: alertsLoading } = useIncidentAlerts(
    incident.id
  );
  const { useMultipleFingerprintsAlertAudit } = useAlerts();
  const { data, isLoading, mutate } = useMultipleFingerprintsAlertAudit(
    alerts?.items.map((m) => m.fingerprint)
  );
  return (
    <AlertTimeline
      auditData={data}
      isLoading={isLoading}
      onRefresh={() => mutate()}
      alert={null}
    />
  );
}
