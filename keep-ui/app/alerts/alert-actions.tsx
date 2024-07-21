import { Button } from "@tremor/react";
import { getSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { AlertDto } from "./models";
import { PlusIcon } from "@radix-ui/react-icons";
import { toast } from "react-toastify";
import { usePresets } from "utils/hooks/usePresets";
import { useRouter } from "next/navigation";
import { SilencedDoorbellNotification } from "@/components/icons";

interface Props {
  selectedRowIds: string[];
  alerts: AlertDto[];
  clearRowSelection: () => void;
  setDismissModalAlert?: (alert: AlertDto[] | null) => void;
}

export default function AlertActions({
  selectedRowIds,
  alerts,
  clearRowSelection,
  setDismissModalAlert,
}: Props) {
  const router = useRouter();
  const { useAllPresets } = usePresets();
  const { mutate: presetsMutator } = useAllPresets({
    revalidateOnFocus: false,
  });

  const selectedAlerts = alerts.filter((_alert, index) =>
    selectedRowIds.includes(index.toString())
  );

  async function addOrUpdatePreset() {
    const newPresetName = prompt("Enter new preset name");
    if (newPresetName) {
      const distinctAlertNames = Array.from(
        new Set(selectedAlerts.map((alert) => alert.name))
      );
      const formattedCel = distinctAlertNames.reduce(
        (accumulator, currentValue, currentIndex) => {
          return (
            accumulator +
            (currentIndex > 0 ? " || " : "") +
            `name == "${currentValue}"`
          );
        },
        ""
      );
      const options = [{ value: formattedCel, label: "CEL" }];
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
    <div className="w-full flex justify-end items-center">
      <Button
        icon={SilencedDoorbellNotification}
        size="xs"
        color="red"
        title="Delete"
        onClick={() => {
          setDismissModalAlert?.(selectedAlerts);
          clearRowSelection();
        }}
      >
        Dismiss {selectedRowIds.length} alert(s)
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
