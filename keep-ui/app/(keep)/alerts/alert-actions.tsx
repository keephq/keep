import { useState } from "react";
import { Button } from "@tremor/react";
import { AlertDto } from "./models";
import { PlusIcon, RocketIcon } from "@radix-ui/react-icons";
import { toast } from "react-toastify";
import { usePresets } from "utils/hooks/usePresets";
import { useRouter } from "next/navigation";
import { SilencedDoorbellNotification } from "@/components/icons";
import AlertAssociateIncidentModal from "./alert-associate-incident-modal";
import CreateIncidentWithAIModal from "./alert-create-incident-ai-modal";
import { useApi } from "@/shared/lib/hooks/useApi";

interface Props {
  selectedRowIds: string[];
  alerts: AlertDto[];
  clearRowSelection: () => void;
  setDismissModalAlert?: (alert: AlertDto[] | null) => void;
  mutateAlerts?: () => void;
}

export default function AlertActions({
  selectedRowIds,
  alerts,
  clearRowSelection,
  setDismissModalAlert,
  mutateAlerts,
}: Props) {
  const router = useRouter();
  const { useAllPresets } = usePresets();
  const api = useApi();
  const { mutate: presetsMutator } = useAllPresets({
    revalidateOnFocus: false,
  });
  const [isIncidentSelectorOpen, setIsIncidentSelectorOpen] =
    useState<boolean>(false);
  const [isCreateIncidentWithAIOpen, setIsCreateIncidentWithAIOpen] =
    useState<boolean>(false);

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
      try {
        const response = await api.post(`/preset`, {
          name: newPresetName,
          options: options,
        });
        toast(`Preset ${newPresetName} created!`, {
          position: "top-left",
          type: "success",
        });
        presetsMutator();
        clearRowSelection();
        router.replace(`/alerts/${newPresetName}`);
      } catch (error) {
        toast(`Error creating preset ${newPresetName}`, {
          position: "top-left",
          type: "error",
        });
      }
    }
  }

  const showIncidentSelector = () => {
    setIsIncidentSelectorOpen(true);
  };
  const hideIncidentSelector = () => {
    setIsIncidentSelectorOpen(false);
  };

  const showCreateIncidentWithAI = () => {
    setIsCreateIncidentWithAIOpen(true);
  };
  const hideCreateIncidentWithAI = () => {
    setIsCreateIncidentWithAIOpen(false);
  };

  const handleSuccessfulAlertsAssociation = () => {
    hideIncidentSelector();
    clearRowSelection();
    if (mutateAlerts) {
      mutateAlerts();
    }
  };

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
      <Button
        icon={PlusIcon}
        size="xs"
        color="orange"
        className="ml-2.5"
        onClick={showIncidentSelector}
        tooltip="Associate events with incident"
      >
        Associate with incident
      </Button>
      <Button
        icon={RocketIcon}
        size="xs"
        color="orange"
        className="ml-2.5"
        onClick={showCreateIncidentWithAI}
        tooltip="Create incidents using AI"
      >
        Create incidents with AI
      </Button>
      <AlertAssociateIncidentModal
        isOpen={isIncidentSelectorOpen}
        alerts={selectedAlerts}
        handleSuccess={handleSuccessfulAlertsAssociation}
        handleClose={hideIncidentSelector}
      />
      <CreateIncidentWithAIModal
        isOpen={isCreateIncidentWithAIOpen}
        alerts={selectedAlerts}
        handleClose={hideCreateIncidentWithAI}
      />
    </div>
  );
}
