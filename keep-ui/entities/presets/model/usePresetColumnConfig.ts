import useSWR, { SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useCallback } from "react";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { ColumnConfiguration } from "./types";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";

type UsePresetColumnConfigOptions = {
  presetId?: string;
  enabled?: boolean; // Flag to control whether to fetch
} & SWRConfiguration;

const DEFAULT_COLUMN_CONFIG: ColumnConfiguration = {
  column_visibility: {},
  column_order: [],
  column_rename_mapping: {},
  column_time_formats: {},
  column_list_formats: {},
};

export const usePresetColumnConfig = ({
  presetId,
  enabled = true,
  ...options
}: UsePresetColumnConfigOptions = {}) => {
  const api = useApi();
  const revalidateMultiple = useRevalidateMultiple();

  const {
    data: columnConfig = DEFAULT_COLUMN_CONFIG,
    isLoading,
    error,
    mutate,
  } = useSWR<ColumnConfiguration>(
    // Only make API call if enabled, API is ready AND presetId is provided
    enabled && api?.isReady?.() && presetId
      ? `/preset/${presetId}/column-config`
      : null,
    async (url) => {
      try {
        const result = await api.get(url);
        return result || DEFAULT_COLUMN_CONFIG;
      } catch (error: any) {
        // If the column config endpoint fails (e.g., 404), return default config
        // This prevents the page from failing to load
        console.warn(
          `Failed to fetch column config for preset ${presetId}:`,
          error
        );
        // Don't throw the error, just return default config
        return DEFAULT_COLUMN_CONFIG;
      }
    },
    {
      fallbackData: DEFAULT_COLUMN_CONFIG,
      // Disable error retries to prevent blocking the page
      shouldRetryOnError: false,
      revalidateOnFocus: false,
      // Return default config on error
      onError: (error) => {
        console.warn("Column config fetch error:", error);
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

      if (!api?.isReady?.()) {
        console.warn("API not ready, cannot update column config");
        return;
      }

      try {
        const response = await api.put(
          `/preset/${presetId}/column-config`,
          config
        );
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
    columnConfig,
    isLoading,
    error,
    updateColumnConfig,
    mutate,
  };
};

export type UsePresetColumnConfigValue = ReturnType<
  typeof usePresetColumnConfig
>;
