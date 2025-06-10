import { Button } from "@tremor/react";
import { AlertDto } from "@/entities/alerts/model";
import { PlusIcon, RocketIcon } from "@radix-ui/react-icons";
import { toast } from "react-toastify";
import { useRouter, useSearchParams } from "next/navigation";
import { SilencedDoorbellNotification } from "@/components/icons";
import { AlertAssociateIncidentModal } from "@/features/alerts/alert-associate-to-incident";
import { CreateIncidentWithAIModal } from "@/features/alerts/alert-create-incident-ai";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Table } from "@tanstack/react-table";

import { useRevalidateMultiple } from "@/shared/lib/state-utils";
import { useConfig } from "@/utils/hooks/useConfig";
import { XMarkIcon } from "@heroicons/react/24/outline";

interface Props {
  selectedAlertsFingerprints: string[];
  table: Table<AlertDto>;
  clearRowSelection: () => void;
  setDismissModalAlert?: (alert: AlertDto[] | null) => void;
  mutateAlerts?: () => void;
  refreshFacets?: () => void;
  setIsIncidentSelectorOpen: (open: boolean) => void;
  isIncidentSelectorOpen: boolean;
  setIsCreateIncidentWithAIOpen: (open: boolean) => void;
  isCreateIncidentWithAIOpen: boolean;
}

export default function AlertActions({
  selectedAlertsFingerprints,
  table,
  clearRowSelection,
  setDismissModalAlert,
  mutateAlerts,
  refreshFacets,
  setIsIncidentSelectorOpen,
  isIncidentSelectorOpen,
  setIsCreateIncidentWithAIOpen,
  isCreateIncidentWithAIOpen,
}: Props) {
  const router = useRouter();
  const api = useApi();
  const { data: config } = useConfig();
  const revalidateMultiple = useRevalidateMultiple();
  const presetsMutator = () => revalidateMultiple(["/preset"]);

  // TODO: refactor
  const searchParams = useSearchParams();
  const createIncidentsFromLastAlerts = searchParams.get(
    "createIncidentsFromLastAlerts"
  );

  const selectedAlerts = table
    .getSelectedRowModel()
    .rows.map((row) => row.original);

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
    if (refreshFacets) {
      refreshFacets();
    }
  };

  const handleSuccessfulAIIncidentCreation = () => {
    hideCreateIncidentWithAI();
    clearRowSelection();
    if (mutateAlerts) {
      mutateAlerts();
    }
    if (refreshFacets) {
      refreshFacets();
    }
  };

  return (
    <div className="w-full flex gap-2.5 justify-end items-center">
      <Button
        icon={XMarkIcon}
        size="xs"
        color="slate"
        title="Clear Selection"
        onClick={clearRowSelection}
      >
        Clear Selection
      </Button>
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
        Dismiss {selectedAlertsFingerprints.length} alert(s)
      </Button>
      <Button
        icon={PlusIcon}
        size="xs"
        color="orange"
        onClick={async () => await addOrUpdatePreset()}
        tooltip="Save current filter as a view"
      >
        Create Preset
      </Button>
      <Button
        icon={PlusIcon}
        size="xs"
        color="orange"
        onClick={showIncidentSelector}
        tooltip="Associate events with incident"
      >
        Associate with incident
      </Button>
      <Button
        icon={RocketIcon}
        size="xs"
        color="orange"
        onClick={showCreateIncidentWithAI}
        tooltip={
          config?.OPEN_AI_API_KEY_SET
            ? "Create incidents with AI"
            : "AI is not configured"
        }
        disabled={!config?.OPEN_AI_API_KEY_SET}
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
        onSuccess={handleSuccessfulAIIncidentCreation}
      />
    </div>
  );
}
