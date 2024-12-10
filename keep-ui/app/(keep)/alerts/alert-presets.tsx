import React, { useState, useEffect } from "react";
import { AlertDto, Preset } from "./models";
import Modal from "@/components/ui/Modal";
import {
  Button,
  Badge,
  Card,
  Subtitle,
  TextInput,
  Switch,
  Text,
} from "@tremor/react";
import { useConfig } from "utils/hooks/useConfig";
import { toast } from "react-toastify";
import { usePresets } from "utils/hooks/usePresets";
import { useTags } from "utils/hooks/useTags";
import { useRouter } from "next/navigation";
import { Table } from "@tanstack/react-table";
import { AlertsRulesBuilder } from "./alerts-rules-builder";
import { formatQuery, parseCEL, RuleGroupType } from "react-querybuilder";
import { useApi } from "@/shared/lib/hooks/useApi";
import CreatableMultiSelect from "@/components/ui/CreatableMultiSelect";
import { MultiValue } from "react-select";
import {
  useCopilotAction,
  useCopilotContext,
  useCopilotReadable,
  CopilotTask,
} from "@copilotkit/react-core";
import { TbSparkles } from "react-icons/tb";
import { useSearchAlerts } from "utils/hooks/useSearchAlerts";
import { Tooltip } from "@/shared/ui/Tooltip";
import { InformationCircleIcon } from "@heroicons/react/24/outline";
import { showErrorToast } from "@/shared/ui/utils/showErrorToast";

interface TagOption {
  id?: number;
  name: string;
}

interface Props {
  presetNameFromApi: string;
  isLoading: boolean;
  table: Table<AlertDto>;
  presetPrivate?: boolean;
  presetNoisy?: boolean;
}

interface AlertsFoundBadgeProps {
  alertsFound: AlertDto[] | undefined; // Updated to use AlertDto type
  isLoading: boolean;
  isDebouncing: boolean;
  vertical?: boolean;
}

export const AlertsFoundBadge: React.FC<AlertsFoundBadgeProps> = ({
  alertsFound,
  isLoading,
  isDebouncing,
  vertical = false,
}) => {
  // Show loading state when searching or debouncing
  if (isLoading || isDebouncing) {
    return (
      <Card className="mt-4">
        <div className="flex justify-center">
          <div
            className={`flex ${
              vertical ? "flex-col" : "flex-row"
            } items-center gap-2`}
          >
            <Badge size="xl" color="orange">
              ...
            </Badge>
            <Text className="text-gray-500 text-sm">Searching...</Text>
          </div>
        </div>
      </Card>
    );
  }

  // Don't show anything if there's no data
  if (!alertsFound) {
    return null;
  }

  return (
    <Card className="mt-4">
      <div className="flex justify-center">
        <div
          className={`flex ${
            vertical ? "flex-col" : "flex-row"
          } items-center gap-2`}
        >
          <Badge size="xl" color="orange">
            {alertsFound.length}
          </Badge>
          <Text className="text-gray-500 text-sm">
            {alertsFound.length === 1 ? "Alert" : "Alerts"} found
          </Text>
        </div>
      </div>
      <Text className="text-center text-xs mt-2">
        These are the alerts that would match your preset
      </Text>
    </Card>
  );
};

interface PresetControlsProps {
  isPrivate: boolean;
  setIsPrivate: (value: boolean) => void;
  isNoisy: boolean;
  setIsNoisy: (value: boolean) => void;
}

export const PresetControls: React.FC<PresetControlsProps> = ({
  isPrivate,
  setIsPrivate,
  isNoisy,
  setIsNoisy,
}) => {
  return (
    <div className="mt-4">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <Switch
            id="private"
            checked={isPrivate}
            onChange={() => setIsPrivate(!isPrivate)}
            color="orange"
          />
          <label htmlFor="private" className="text-sm text-gray-500">
            <Text>Private</Text>
          </label>
          <Tooltip
            content={<>Private presets are only visible to you</>}
            className="z-50"
          >
            <InformationCircleIcon className="w-4 h-4" />
          </Tooltip>
        </div>

        <div className="flex items-center gap-2">
          <Switch
            id="noisy"
            checked={isNoisy}
            onChange={() => setIsNoisy(!isNoisy)}
            color="orange"
          />
          <label htmlFor="noisy" className="text-sm text-gray-500">
            <Text>Noisy</Text>
          </label>
          <Tooltip
            content={
              <>Noisy presets will trigger sound for every matching event</>
            }
            className="z-50"
          >
            <InformationCircleIcon className="w-4 h-4" />
          </Tooltip>
        </div>
      </div>
    </div>
  );
};

export default function AlertPresets({
  presetNameFromApi,
  isLoading,
  table,
  presetPrivate = false,
  presetNoisy = false,
}: Props) {
  const api = useApi();
  const { useAllPresets } = usePresets();
  const { mutate: presetsMutator, data: savedPresets = [] } = useAllPresets({
    revalidateOnFocus: false,
  });
  const { data: tags = [], mutate: mutateTags } = useTags();
  const router = useRouter();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [presetName, setPresetName] = useState(
    presetNameFromApi === "feed" || presetNameFromApi === "deleted"
      ? ""
      : presetNameFromApi
  );
  const [isPrivate, setIsPrivate] = useState(presetPrivate);
  const [isNoisy, setIsNoisy] = useState(presetNoisy);
  const [presetCEL, setPresetCEL] = useState("");

  // Create
  const defaultQuery: RuleGroupType = parseCEL(presetCEL) as RuleGroupType;

  // Parse CEL to RuleGroupType or use default empty rule group
  const parsedQuery = presetCEL
    ? (parseCEL(presetCEL) as RuleGroupType)
    : defaultQuery;

  // Add useSearchAlerts hook with proper typing
  const { data: alertsFound, isLoading: isSearching } = useSearchAlerts({
    query: parsedQuery,
    timeframe: 0,
  });

  const [generatingName, setGeneratingName] = useState(false);
  const [selectedTags, setSelectedTags] = useState<TagOption[]>([]);
  const [newTags, setNewTags] = useState<string[]>([]); // New tags created during the session
  const { data: configData } = useConfig();

  const isAIEnabled = configData?.OPEN_AI_API_KEY_SET;
  const context = useCopilotContext();

  useCopilotReadable({
    description: "The CEL query for the alert preset",
    value: presetCEL,
  });

  useCopilotAction({
    name: "setGeneratedName",
    description: "Set the generated preset name",
    parameters: [
      { name: "name", type: "string", description: "The generated name" },
    ],
    handler: async ({ name }) => {
      setPresetName(name);
    },
  });

  const generatePresetName = async () => {
    setGeneratingName(true);
    const task = new CopilotTask({
      instructions:
        "Generate a short, descriptive name for an alert preset based on the provided CEL query. The name should be concise but meaningful, reflecting the key conditions in the query.",
    });
    await task.run(context);
    setGeneratingName(false);
  };

  const selectedPreset = savedPresets.find(
    (savedPreset) =>
      savedPreset.name.toLowerCase() ===
      decodeURIComponent(presetNameFromApi).toLowerCase()
  ) as Preset | undefined;

  useEffect(() => {
    if (selectedPreset) {
      setSelectedTags(
        selectedPreset.tags.map((tag) => ({ id: tag.id, name: tag.name }))
      );
    }
  }, [selectedPreset]);

  async function deletePreset(presetId: string) {
    if (
      confirm(
        `You are about to delete preset ${presetNameFromApi}, are you sure?`
      )
    ) {
      try {
        const response = await api.delete(`/preset/${presetId}`);
        toast(`Preset ${presetNameFromApi} deleted!`, {
          position: "top-left",
          type: "success",
        });
        presetsMutator();
        router.push("/alerts/feed");
      } catch (error) {
        toast(`Error deleting preset ${presetNameFromApi}`, {
          position: "top-left",
          type: "error",
        });
      }
    }
  }

  async function addOrUpdatePreset() {
    if (!presetName) return;

    let sqlQuery;
    try {
      sqlQuery = formatQuery(parseCEL(presetCEL), {
        format: "parameterized_named",
        parseNumbers: true,
      });
    } catch (error) {
      showErrorToast(error, "Failed to parse the CEL query");
      return;
    }
    const body = {
      name: presetName,
      options: [
        {
          label: "CEL",
          value: presetCEL,
        },
        {
          label: "SQL",
          value: sqlQuery,
        },
      ],
      is_private: isPrivate,
      is_noisy: isNoisy,
      tags: selectedTags.map((tag) => ({
        id: tag.id,
        name: tag.name,
      })),
    };

    try {
      const response = selectedPreset?.id
        ? await api.put(`/preset/${selectedPreset?.id}`, body)
        : await api.post(`/preset`, body);
      setIsModalOpen(false);
      await presetsMutator();
      await mutateTags();
      router.replace(`/alerts/${encodeURIComponent(presetName.toLowerCase())}`);
      toast(
        selectedPreset
          ? `Preset ${presetName} updated!`
          : `Preset ${presetName} created!`,
        {
          position: "top-left",
          type: "success",
        }
      );
    } catch (error) {
      showErrorToast(error, "Failed to update preset");
    }
  }

  const handleCreateTag = (inputValue: string) => {
    const newTag = { name: inputValue };
    setNewTags((prevTags) => [...prevTags, inputValue]);
    setSelectedTags((prevTags) => [...prevTags, newTag]);
  };

  const handleChange = (
    newValue: MultiValue<{ value: string; label: string }>
  ) => {
    setSelectedTags(
      newValue.map((tag) => ({
        id: tags.find((t) => t.name === tag.value)?.id,
        name: tag.value,
      }))
    );
  };

  // Handle modal close
  const handleModalClose = () => {
    setIsModalOpen(false);
    setPresetName("");
    setPresetCEL("");
  };

  return (
    <>
      <Modal
        isOpen={isModalOpen}
        onClose={handleModalClose}
        className="w-[30%] max-w-screen-2xl max-h-[710px] transform overflow-auto ring-tremor bg-white p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
      >
        <div className="space-y-2">
          <div className="text-lg font-semibold">
            <p>{presetName ? "Update preset" : "Enter new preset name"}</p>
          </div>

          <div className="space-y-2">
            <Subtitle>Preset Name</Subtitle>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <TextInput
                  // TODO: don't show error until user tries to save
                  error={!presetName}
                  errorMessage="Preset name is required"
                  placeholder={
                    presetName === "feed" || presetName === "deleted"
                      ? ""
                      : presetName
                  }
                  value={presetName}
                  onChange={(e) => setPresetName(e.target.value)}
                  className="w-full"
                />
                {isAIEnabled && (
                  <Button
                    variant="secondary"
                    onClick={generatePresetName}
                    disabled={!presetCEL || generatingName}
                    loading={generatingName}
                    icon={TbSparkles}
                    size="xs"
                  >
                    AI
                  </Button>
                )}
              </div>
            </div>
            <PresetControls
              isPrivate={isPrivate}
              setIsPrivate={setIsPrivate}
              isNoisy={isNoisy}
              setIsNoisy={setIsNoisy}
            />
          </div>
          <Subtitle>Tags</Subtitle>
          <CreatableMultiSelect
            value={selectedTags.map((tag) => ({
              value: tag.name,
              label: tag.name,
            }))}
            onChange={handleChange}
            onCreateOption={handleCreateTag}
            options={tags.map((tag) => ({
              value: tag.name,
              label: tag.name,
            }))}
            placeholder="Select or create tags"
          />

          {/* Add alerts count card before the save buttons */}
          {presetCEL && (
            <div className="mt-4">
              <AlertsFoundBadge
                alertsFound={alertsFound}
                isLoading={isSearching}
                isDebouncing={false}
                vertical={true}
              />
            </div>
          )}

          <div className="flex justify-end space-x-2.5">
            <Button
              size="lg"
              variant="secondary"
              color="orange"
              onClick={handleModalClose}
              tooltip="Close"
            >
              Close
            </Button>
            <Button
              size="lg"
              color="orange"
              onClick={addOrUpdatePreset}
              tooltip="Save Preset"
            >
              Save
            </Button>
          </div>
        </div>
      </Modal>
      <div className="flex w-full items-start relative z-10">
        <AlertsRulesBuilder
          table={table}
          defaultQuery=""
          selectedPreset={selectedPreset}
          setIsModalOpen={setIsModalOpen}
          deletePreset={deletePreset}
          setPresetCEL={setPresetCEL}
        />
      </div>
    </>
  );
}
