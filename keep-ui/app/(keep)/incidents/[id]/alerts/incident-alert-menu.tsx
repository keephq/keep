import { Button, Icon } from "@tremor/react";
import { AlertDto } from "@/app/(keep)/alerts/models";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { toast } from "react-toastify";
import { useApiUrl, useConfig } from "utils/hooks/useConfig";
import { useIncidentAlerts } from "utils/hooks/useIncidents";
import { LinkSlashIcon } from "@heroicons/react/24/outline";
import { ReadOnlyAwareToaster } from "@/shared/lib/ReadOnlyAwareToaster";

interface Props {
  incidentId: string;
  alert: AlertDto;
}
export default function IncidentAlertMenu({ incidentId, alert }: Props) {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();
  const { mutate } = useIncidentAlerts(incidentId);
  const { data: configData } = useConfig();

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
          ReadOnlyAwareToaster.error(
            "Failed to remove alert from incident, please contact us if this issue persists.",
            configData,
            {
              position: "top-right",
            }
          );
        }
      });
    }
  }

  return (
    <div className="">
      <Button
        variant="light"
        size="xs"
        icon={LinkSlashIcon}
        color="red"
        tooltip="Remove correlation"
        className="cursor-pointer"
        onClick={onRemove}
      >
        Remove correlation
      </Button>
    </div>
  );
}
