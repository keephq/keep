import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui/utils/showErrorToast";
import { showSuccessToast } from "@/shared/ui/utils/showSuccessToast";
import { useCallback } from "react";
import { formatQuery, parseCEL } from "react-querybuilder";
import { PresetCreateUpdateDto } from "./types";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";

function createPresetBody(data: PresetCreateUpdateDto) {
  let sqlQuery;
  try {
    sqlQuery = formatQuery(parseCEL(data.CEL), {
      format: "parameterized_named",
      parseNumbers: true,
    });
  } catch (error) {
    showErrorToast(error, "Failed to parse the CEL query");
    return;
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
      const body = createPresetBody(data);

      try {
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
      const body = createPresetBody(data);
      try {
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
    async (presetId: string) => {
      const presetName = "";
      if (
        confirm(`You are about to delete preset ${presetName}, are you sure?`)
      ) {
        try {
          const response = await api.delete(`/preset/${presetId}`);
          showSuccessToast(`Preset ${presetName} deleted!`);
          mutatePresetsList();
        } catch (error) {
          showErrorToast(error, `Error deleting preset ${presetName}`);
        }
      }
    },
    [api, mutatePresetsList]
  );

  return {
    createPreset,
    updatePreset,
    deletePreset,
  };
}
