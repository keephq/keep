import { TrashIcon } from "@radix-ui/react-icons";
import { Icon } from "@tremor/react";
import { AlertDto } from "app/alerts/models";
import { useSession } from "next-auth/react";
import { toast } from "react-toastify";
import { getApiURL } from "utils/apiUrl";
import { useIncidentAlerts } from "utils/hooks/useIncidents";

interface Props {
  incidentId: string;
  alert: AlertDto;
}
export default function IncidentAlertMenu({ incidentId, alert }: Props) {
  const apiUrl = getApiURL();
  const { data: session } = useSession();
  const { mutate } = useIncidentAlerts(incidentId);

  function onRemove() {
    if (confirm("Are you sure you want to remove correlation?")) {
      fetch(`${apiUrl}/incidents/${incidentId}/alerts`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify([alert.event_id]),
      }).then((response) => {
        if (response.ok) {
          toast.success("Alert removed from incident successfully", {
            position: "top-right",
          });
          mutate();
        } else {
          toast.error(
            "Failed to remove alert from incident, please contact us if this issue persists.",
            {
              position: "top-right",
            }
          );
        }
      });
    }
  }

  return (
    <div className="flex flex-col">
      <Icon
        icon={TrashIcon}
        color="red"
        tooltip="Remove"
        className="cursor-pointer"
        onClick={onRemove}
      />
    </div>
  );
}
