import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { useCallback } from "react";
import { formatQuery } from "react-querybuilder";
import { parseCEL } from "react-querybuilder/parseCEL";
import { Preset, PresetCreateUpdateDto } from "./types";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { LOCAL_PRESETS_KEY } from "./constants";

function createPresetBody(data: PresetCreateUpdateDto) {
  let sqlQuery;
  try {
    sqlQuery = formatQuery(parseCEL(data.CEL), {
      format: "parameterized_named",
      parseNumbers: true,
    });
  } catch (error) {
    throw new Error("Failed to parse the CEL query");
  }
  return {
    name: data.name,
    options: [
      { label: "CEL", value: data.CEL },
      { label: "SQL", value: sqlQuery },
    ],
    is_private: data.isPrivate,
    is_noisy: data.isNoisy,
    tags: data.tags,
  };
}

export function usePresetActions() {
  const api = useApi();
  const [_, setLocalDynamicPresets] = useLocalStorage<Preset[]>(
    LOCAL_PRESETS_KEY,
    []
  );
  const revalidateMultiple = useRevalidateMultiple();
  const mutatePresetsList = useCallback(
    () => revalidateMultiple(["/preset", "/preset?"]),
    [revalidateMultiple]
  );
  const mutateTags = useCallback(
    () => revalidateMultiple(["/tags"]),
    [revalidateMultiple]
  );

  const createPreset = useCallback(
    async (data: PresetCreateUpdateDto) => {
      try {
        const body = createPresetBody(data);
        const response = await api.post(`/preset`, body);
        mutatePresetsList();
        mutateTags();
        showSuccessToast(`Preset ${data.name} created!`);
        return response;
      } catch (error) {
        showErrorToast(error, "Failed to create preset");
      }
    },
    [api, mutatePresetsList, mutateTags]
  );

  const updatePreset = useCallback(
    async (presetId: string, data: PresetCreateUpdateDto) => {
      try {
        const body = createPresetBody(data);
        const response = await api.put(`/preset/${presetId}`, body);
        mutatePresetsList();
        mutateTags();
        showSuccessToast(`Preset ${data.name} updated!`);
        return response;
      } catch (error) {
        showErrorToast(error, "Failed to update preset");
      }
    },
    [api, mutatePresetsList, mutateTags]
  );

  const deletePreset = useCallback(
    async (presetId: string, presetName: string) => {
      const isDeleteConfirmed = confirm(
        `You are about to delete preset ${presetName}. Are you sure?`
      );
      if (!isDeleteConfirmed) {
        return;
      }
      try {
        const response = await api.delete(`/preset/${presetId}`);
        showSuccessToast(`Preset ${presetName} deleted!`);
        mutatePresetsList();
        setLocalDynamicPresets((oldOrder) =>
          oldOrder.filter((p) => p.id !== presetId)
        );
      } catch (error) {
        showErrorToast(error, `Error deleting preset ${presetName}`);
      }
    },
    [api, mutatePresetsList, setLocalDynamicPresets]
  );

  return {
    createPreset,
    updatePreset,
    deletePreset,
  };
}
