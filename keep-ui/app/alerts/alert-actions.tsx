import { TrashIcon } from "@heroicons/react/24/outline";
import { Button } from "@tremor/react";
import { getSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { AlertDto } from "./models";
import { useAlerts } from "utils/hooks/useAlerts";

interface Props {
  selectedRowIds: string[];
  alerts: AlertDto[];
}

export default function AlertActions({ selectedRowIds, alerts }: Props) {
  const { useAllAlerts } = useAlerts();
  const { mutate } = useAllAlerts();

  const onDelete = async () => {
    const confirmed = confirm(
      `Are you sure you want to delete ${selectedRowIds.length} alert(s)?`
    );

    if (confirmed) {
      const session = await getSession();
      const apiUrl = getApiURL();

      const selectedAlerts = alerts.filter((_alert, index) =>
        selectedRowIds.includes(index.toString())
      );

      for await (const alert of selectedAlerts) {
        const { fingerprint } = alert;

        const body = {
          fingerprint,
          lastReceived: alert.lastReceived,
          restore: false,
        };

        const res = await fetch(`${apiUrl}/alerts`, {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${session!.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(body),
        });
        if (res.ok) {
          await mutate();
        }
      }
    }
  };

  return (
    <div className="w-full flex justify-end items-center py-0.5">
      <Button
        icon={TrashIcon}
        size="xs"
        color="red"
        title="Delete"
        onClick={onDelete}
      >
        Delete {selectedRowIds.length} alert(s)
      </Button>
    </div>
  );
}
