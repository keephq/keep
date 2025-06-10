import useSWR, { SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useCallback } from "react";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { ColumnConfiguration } from "./types";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";

type UsePresetColumnConfigOptions = {
  presetId?: string;
} & SWRConfiguration;

export const usePresetColumnConfig = ({ 
  presetId, 
  ...options 
}: UsePresetColumnConfigOptions = {}) => {
  const api = useApi();
  const revalidateMultiple = useRevalidateMultiple();

  const {
    data: columnConfig,
    isLoading,
    error,
    mutate,
  } = useSWR<ColumnConfiguration>(
    api.isReady() && presetId ? `/preset/${presetId}/column-config` : null,
    (url) => api.get(url),
    {
      fallbackData: {
        column_visibility: {},
        column_order: [],
        column_rename_mapping: {},
        column_time_formats: {},
        column_list_formats: {},
      },
      ...options,
    }
  );

  const updateColumnConfig = useCallback(
    async (config: Partial<ColumnConfiguration>) => {
      if (!presetId) {
        showErrorToast("No preset ID provided");
        return;
      }

      try {
        const response = await api.put(`/preset/${presetId}/column-config`, config);
        showSuccessToast("Column configuration saved!");
        mutate();
        // Also revalidate preset list to update any cached data
        revalidateMultiple(["/preset", "/preset?"]);
        return response;
      } catch (error) {
        showErrorToast(error, "Failed to save column configuration");
        throw error;
      }
    },
    [api, presetId, mutate, revalidateMultiple]
  );

  return {
    columnConfig: columnConfig || {
      column_visibility: {},
      column_order: [],
      column_rename_mapping: {},
      column_time_formats: {},
      column_list_formats: {},
    },
    isLoading,
    error,
    updateColumnConfig,
    mutate,
  };
};

export type UsePresetColumnConfigValue = ReturnType<typeof usePresetColumnConfig>;