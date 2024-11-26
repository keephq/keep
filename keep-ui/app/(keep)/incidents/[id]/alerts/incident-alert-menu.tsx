import { Badge } from "@tremor/react";
import { AlertDto } from "@/app/(keep)/alerts/models";
import { toast } from "react-toastify";
import { useIncidentAlerts } from "utils/hooks/useIncidents";
import { LiaUnlinkSolid } from "react-icons/lia";
import { useApi } from "@/shared/lib/hooks/useApi";

interface Props {
  incidentId: string;
  alert: AlertDto;
}
export default function IncidentAlertMenu({ incidentId, alert }: Props) {
  const api = useApi();
  const { mutate } = useIncidentAlerts(incidentId);

  function onRemove() {
    if (confirm("Are you sure you want to remove correlation?")) {
      api
        .delete(`/incidents/${incidentId}/alerts`, {
          body: [alert.event_id],
        })
        .then(() => {
          toast.success("Alert removed from incident successfully", {
            position: "top-right",
          });
          mutate();
        })
        .catch((error) => {
          toast.error(
            "Failed to remove alert from incident, please contact us if this issue persists.",
            {
              position: "top-right",
            }
          );
        });
    }
  }

  return (
    <div className="flex flex-col">
      <Badge
        icon={LiaUnlinkSolid}
        color="red"
        tooltip="Remove correlation"
        className="cursor-pointer"
        onClick={onRemove}
      >
        Unlink
      </Badge>
    </div>
  );
}
