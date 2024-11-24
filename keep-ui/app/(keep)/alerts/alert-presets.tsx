import React, { useState, useEffect } from "react";
import { AlertDto, Preset } from "./models";
import Modal from "@/components/ui/Modal";
import { Button, Subtitle, TextInput, Switch, Text } from "@tremor/react";
import { useApiUrl } from "utils/hooks/useConfig";
import { toast } from "react-toastify";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { usePresets } from "utils/hooks/usePresets";
import { useTags } from "utils/hooks/useTags";
import { useRouter } from "next/navigation";
import { Table } from "@tanstack/react-table";
import { AlertsRulesBuilder } from "./alerts-rules-builder";
import QueryBuilder, { formatQuery, parseCEL } from "react-querybuilder";
import CreatableMultiSelect from "@/components/ui/CreatableMultiSelect";
import { MultiValue } from "react-select";

type OptionType = { value: string; label: string };

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

export default function AlertPresets({
  presetNameFromApi,
  isLoading,
  table,
  presetPrivate = false,
  presetNoisy = false,
}: Props) {
  const apiUrl = useApiUrl();
  const { useAllPresets } = usePresets();
  const { mutate: presetsMutator, data: savedPresets = [] } = useAllPresets({
    revalidateOnFocus: false,
  });
  const { data: session } = useSession();
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
  const [selectedTags, setSelectedTags] = useState<TagOption[]>([]);
  const [newTags, setNewTags] = useState<string[]>([]); // New tags created during the session

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
      const response = await fetch(`${apiUrl}/preset/${presetId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });
      if (response.ok) {
        toast(`Preset ${presetNameFromApi} deleted!`, {
          position: "top-left",
          type: "success",
        });
        presetsMutator();
        router.push("/alerts/feed");
      }
    }
  }

  async function addOrUpdatePreset() {
    if (presetName) {
      // Translate the CEL to SQL
      const sqlQuery = formatQuery(parseCEL(presetCEL), {
        format: "parameterized_named",
        parseNumbers: true,
      });

      const response = await fetch(
        selectedPreset?.id
          ? `${apiUrl}/preset/${selectedPreset?.id}`
          : `${apiUrl}/preset`,
        {
          method: selectedPreset?.id ? "PUT" : "POST",
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
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
          }),
        }
      );
      if (response.ok) {
        setIsModalOpen(false);
        toast(
          selectedPreset
            ? `Preset ${presetName} updated!`
            : `Preset ${presetName} created!`,
          {
            position: "top-left",
            type: "success",
          }
        );
        presetsMutator();
        mutateTags();
        router.push(`/alerts/${presetName.toLowerCase()}`);
      }
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

  return (
    <>
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        className="w-[30%] max-w-screen-2xl max-h-[710px] transform overflow-auto ring-tremor bg-white p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
      >
        <div className="space-y-2">
          <div className="text-lg font-semibold">
            <p>{presetName ? "Update preset" : "Enter new preset name"}</p>
          </div>

          <div className="space-y-2">
            <Subtitle>Preset Name</Subtitle>
            <TextInput
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

          <div className="flex items-center space-x-2">
            <Switch
              id={"private"}
              checked={isPrivate}
              onChange={() => setIsPrivate(!isPrivate)}
              color={"orange"}
            />
            <label htmlFor="private" className="text-sm text-gray-500">
              <Text>Private</Text>
            </label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id={"noisy"}
              checked={isNoisy}
              onChange={() => setIsNoisy(!isNoisy)}
              color={"orange"}
            />
            <label htmlFor="noisy" className="text-sm text-gray-500">
              <Text>Noisy</Text>
            </label>
          </div>

          <div className="flex justify-end space-x-2.5">
            <Button
              size="lg"
              variant="secondary"
              color="orange"
              onClick={() => setIsModalOpen(false)}
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
