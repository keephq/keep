import { useReactTable } from "@tanstack/react-table";
import { useIncidentAlerts } from "utils/hooks/useIncidents";

interface Props {
  incidentFingerprint: string;
}
export default function IncidentAlerts({ incidentFingerprint }: Props) {
  const {
    data: alerts,
    isLoading,
    error,
  } = useIncidentAlerts(incidentFingerprint);
  const table = useReactTable();
  return <></>;
}
