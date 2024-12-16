import { Button } from "@/components/ui";
import { useConfig } from "@/utils/hooks/useConfig";
import {
  useCopilotAction,
  useCopilotContext,
  useCopilotReadable,
} from "@copilotkit/react-core";
import { CopilotTask } from "@copilotkit/react-core";
import { Subtitle, TextInput } from "@tremor/react";
import { useCallback, useState } from "react";
import { PresetControls } from "./preset-controls";
import CreatableMultiSelect from "@/components/ui/CreatableMultiSelect";
import { AlertsCountBadge } from "./alerts-count-badge";
import { TbSparkles } from "react-icons/tb";
import { MultiValue } from "react-select";
import { useTags } from "@/utils/hooks/useTags";
import { Preset } from "@/entities/presets/model/types";
import { usePresetActions } from "@/entities/presets/model/usePresetActions";

interface TagOption {
  id?: string;
  name: string;
}

type CreateOrUpdatePresetFormProps = {
  presetId: string | null;
  presetData: {
    CEL: string;
    name: string | undefined;
    isPrivate: boolean | undefined;
    isNoisy: boolean | undefined;
    tags: TagOption[] | undefined;
  };
  onCreateOrUpdate?: (preset: Preset) => void;
  onCancel?: () => void;
};

export function CreateOrUpdatePresetForm({
  presetId,
  presetData,
  onCreateOrUpdate,
  onCancel,
}: CreateOrUpdatePresetFormProps) {
  const [presetName, setPresetName] = useState(presetData.name ?? "");
  const [isPrivate, setIsPrivate] = useState(presetData.isPrivate ?? false);
  const [isNoisy, setIsNoisy] = useState(presetData.isNoisy ?? false);

  const [generatingName, setGeneratingName] = useState(false);
  const [selectedTags, setSelectedTags] = useState<TagOption[]>(
    presetData.tags ?? []
  );
  const [newTags, setNewTags] = useState<string[]>([]); // New tags created during the session

  const clearForm = () => {
    setPresetName("");
    setIsPrivate(false);
    setIsNoisy(false);
    setSelectedTags([]);
    setNewTags([]);
  };

  const handleCancel = () => {
    clearForm();
    onCancel?.();
  };

  const { data: tags = [] } = useTags();

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

  const { data: configData } = useConfig();
  const isAIEnabled = configData?.OPEN_AI_API_KEY_SET;
  const context = useCopilotContext();

  useCopilotReadable({
    description: "The CEL query for the alert preset",
    value: presetData.CEL,
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

  const generatePresetName = useCallback(async () => {
    setGeneratingName(true);
    const task = new CopilotTask({
      instructions:
        "Generate a short, descriptive name for an alert preset based on the provided CEL query. The name should be concise but meaningful, reflecting the key conditions in the query.",
    });
    await task.run(context);
    setGeneratingName(false);
  }, [context]);

  const { createPreset, updatePreset } = usePresetActions();
  const addOrUpdatePreset = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (presetId) {
      const updatedPreset = await updatePreset(presetId, {
        ...presetData,
        name: presetName,
        isPrivate,
        isNoisy,
        tags: selectedTags.map((tag) => ({
          id: tag.id,
          name: tag.name,
        })),
      });
      onCreateOrUpdate?.(updatedPreset);
    } else {
      const newPreset = await createPreset({
        ...presetData,
        name: presetName,
        isPrivate,
        isNoisy,
        tags: selectedTags.map((tag) => ({
          id: tag.id,
          name: tag.name,
        })),
      });
      onCreateOrUpdate?.(newPreset);
    }
  };

  return (
    <form className="space-y-2" onSubmit={addOrUpdatePreset}>
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
                disabled={!presetData.CEL || generatingName}
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
      {presetData.CEL && (
        <div className="mt-4">
          <AlertsCountBadge
            presetCEL={presetData.CEL}
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
          onClick={handleCancel}
          tooltip="Close"
        >
          Close
        </Button>
        <Button
          size="lg"
          color="orange"
          variant="primary"
          tooltip="Save Preset"
        >
          Save
        </Button>
      </div>
    </form>
  );
}
