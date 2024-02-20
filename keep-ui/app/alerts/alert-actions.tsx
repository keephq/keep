import { TrashIcon } from "@heroicons/react/24/outline";
import { Button } from "@tremor/react";
import { getSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { AlertDto } from "./models";
import { useAlerts } from "utils/hooks/useAlerts";
import { PlusIcon } from "@radix-ui/react-icons";
import { toast } from "react-toastify";
import { usePresets } from "utils/hooks/usePresets";
import { usePathname, useRouter } from "next/navigation";

interface Props {
  selectedRowIds: string[];
  alerts: AlertDto[];
  clearRowSelection: () => void;
}

export default function AlertActions({
  selectedRowIds,
  alerts,
  clearRowSelection,
}: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const { useAllAlerts } = useAlerts();
  const { mutate } = useAllAlerts({ revalidateOnFocus: false });
  const { useAllPresets } = usePresets();
  const { mutate: presetsMutator } = useAllPresets({
    revalidateOnFocus: false,
  });

  const selectedAlerts = alerts.filter((_alert, index) =>
    selectedRowIds.includes(index.toString())
  );

  const onDelete = async () => {
    const confirmed = confirm(
      `Are you sure you want to delete ${selectedRowIds.length} alert(s)?`
    );

    if (!confirmed) {
      return;
    }

    const session = await getSession();
    if (!session) {
      toast(`Session expired.`, {
        position: "top-left",
        type: "error",
      });
      return;
    }

    const apiUrl = getApiURL();
    const headers = {
      Authorization: `Bearer ${session.accessToken}`,
      "Content-Type": "application/json",
    };

    const deletionPromises = selectedAlerts.map((alert) =>
      fetch(`${apiUrl}/alerts`, {
        method: "DELETE",
        headers,
        body: JSON.stringify({
          fingerprint: alert.fingerprint,
          lastReceived: alert.lastReceived,
          restore: false,
        }),
      })
    );

    const results = await Promise.allSettled(deletionPromises);

    const allSucceeded = results.every(
      (result) => result.status === "fulfilled" && result.value.ok
    );

    if (allSucceeded) {
      toast(`${selectedRowIds.length} alert(s) deleted!`, {
        position: "top-left",
        type: "success",
      });
      mutate();
      clearRowSelection();
    } else {
      toast(`Error deleting alerts`, {
        position: "top-left",
        type: "error",
      });
    }
  };

  async function addOrUpdatePreset() {
    const newPresetName = prompt("Enter new preset name");
    if (newPresetName) {
      const distinctAlertNames = Array.from(
        new Set(selectedAlerts.map((alert) => alert.name))
      );
      const options = distinctAlertNames.map((name) => {
        return { value: `name=${name}`, label: `name=${name}` };
      });
      const session = await getSession();
      const apiUrl = getApiURL();
      const response = await fetch(`${apiUrl}/preset`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: newPresetName, options: options }),
      });
      if (response.ok) {
        toast(`Preset ${newPresetName} created!`, {
          position: "top-left",
          type: "success",
        });
        presetsMutator();
        clearRowSelection();
        router.replace(`/alerts/${newPresetName}`);
      } else {
        toast(`Error creating preset ${newPresetName}`, {
          position: "top-left",
          type: "error",
        });
      }
    }
  }

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
      <Button
        icon={PlusIcon}
        size="xs"
        color="orange"
        className="ml-2.5"
        onClick={async () => await addOrUpdatePreset()}
        tooltip="Save current filter as a view"
      >
        Create Preset
      </Button>
    </div>
  );
}
