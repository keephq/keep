import { useCallback, useMemo } from "react";
import { VisibilityState, ColumnOrderState } from "@tanstack/react-table";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { usePresetColumnConfig } from "./usePresetColumnConfig";
import { TimeFormatOption } from "@/widgets/alerts-table/lib/alert-table-time-format";
import { ListFormatOption } from "@/widgets/alerts-table/lib/alert-table-list-format";
import { ColumnRenameMapping } from "@/widgets/alerts-table/ui/alert-table-column-rename";
import {
  DEFAULT_COLS,
  DEFAULT_COLS_VISIBILITY,
} from "@/widgets/alerts-table/lib/alert-table-utils";
import { STATIC_PRESETS_NAMES, STATIC_PRESET_IDS } from "./constants";
import { ColumnConfiguration } from "./types";

interface UsePresetColumnStateOptions {
  presetName: string;
  presetId?: string;
  useBackend?: boolean; // Flag to enable backend usage
}

export const usePresetColumnState = ({
  presetName,
  presetId,
  useBackend = false,
}: UsePresetColumnStateOptions) => {
  // Check if this is a static preset that should always use local storage
  // Check both by ID and by name as fallbacks
  const isStaticPreset =
    !presetId ||
    STATIC_PRESET_IDS.includes(presetId) ||
    STATIC_PRESETS_NAMES.includes(presetName);
  const shouldUseBackend = useBackend && !isStaticPreset && !!presetId;

  // Backend-based state - always call hook but conditionally enable fetching
  const { columnConfig, updateColumnConfig, isLoading, error } =
    usePresetColumnConfig({
      presetId, // Always pass presetId, let the hook decide internally
      enabled: shouldUseBackend, // Use enabled flag to control fetching
    });

  // Local storage fallbacks (existing implementation)
  const [localColumnVisibility, setLocalColumnVisibility] =
    useLocalStorage<VisibilityState>(
      `column-visibility-${presetName}`,
      DEFAULT_COLS_VISIBILITY
    );

  const [localColumnOrder, setLocalColumnOrder] =
    useLocalStorage<ColumnOrderState>(
      `column-order-${presetName}`,
      DEFAULT_COLS
    );

  const [localColumnRenameMapping, setLocalColumnRenameMapping] =
    useLocalStorage<ColumnRenameMapping>(
      `column-rename-mapping-${presetName}`,
      {}
    );

  const [localColumnTimeFormats, setLocalColumnTimeFormats] = useLocalStorage<
    Record<string, TimeFormatOption>
  >(`column-time-formats-${presetName}`, {});

  const [localColumnListFormats, setLocalColumnListFormats] = useLocalStorage<
    Record<string, ListFormatOption>
  >(`column-list-formats-${presetName}`, {});

  // Determine which state to use - with fallback to local storage on error
  // Always return immediately with either backend or local data
  const columnVisibility = useMemo(() => {
    // If we shouldn't use backend or there's an error, use local storage immediately
    if (!shouldUseBackend || error) {
      return localColumnVisibility;
    }
    // If backend is loading, return defaults to avoid blocking render
    // Once loaded, backend config will be used
    return {
      ...DEFAULT_COLS_VISIBILITY,
      ...(columnConfig?.column_visibility || {}),
    };
  }, [
    shouldUseBackend,
    columnConfig?.column_visibility,
    localColumnVisibility,
    error,
  ]);

  const columnOrder = useMemo(() => {
    // If we shouldn't use backend or there's an error, use local storage immediately
    if (!shouldUseBackend || error) {
      return localColumnOrder;
    }
    // For backend presets, use backend order if available, otherwise default
    return columnConfig?.column_order && columnConfig.column_order.length > 0
      ? columnConfig.column_order
      : DEFAULT_COLS;
  }, [shouldUseBackend, columnConfig?.column_order, localColumnOrder, error]);

  const columnRenameMapping = useMemo(() => {
    // If we shouldn't use backend or there's an error, use local storage immediately
    if (!shouldUseBackend || error) {
      return localColumnRenameMapping;
    }
    return columnConfig?.column_rename_mapping || {};
  }, [
    shouldUseBackend,
    columnConfig?.column_rename_mapping,
    localColumnRenameMapping,
    error,
  ]);

  const columnTimeFormats = useMemo(() => {
    // If we shouldn't use backend or there's an error, use local storage immediately
    if (!shouldUseBackend || error) {
      return localColumnTimeFormats;
    }
    return (columnConfig?.column_time_formats || {}) as Record<
      string,
      TimeFormatOption
    >;
  }, [
    shouldUseBackend,
    columnConfig?.column_time_formats,
    localColumnTimeFormats,
    error,
  ]);

  const columnListFormats = useMemo(() => {
    // If we shouldn't use backend or there's an error, use local storage immediately
    if (!shouldUseBackend || error) {
      return localColumnListFormats;
    }
    return (columnConfig?.column_list_formats || {}) as Record<
      string,
      ListFormatOption
    >;
  }, [
    shouldUseBackend,
    columnConfig?.column_list_formats,
    localColumnListFormats,
    error,
  ]);

  // Batched update function to avoid multiple API calls
  const updateMultipleColumnConfigs = useCallback(
    async (updates: {
      columnVisibility?: VisibilityState;
      columnOrder?: ColumnOrderState;
      columnRenameMapping?: ColumnRenameMapping;
      columnTimeFormats?: Record<string, TimeFormatOption>;
      columnListFormats?: Record<string, ListFormatOption>;
    }) => {
      if (shouldUseBackend && !error) {
        // Batch all updates into a single API call
        const batchedUpdate: Partial<ColumnConfiguration> = {};

        if (updates.columnVisibility !== undefined) {
          batchedUpdate.column_visibility = updates.columnVisibility;
        }
        if (updates.columnOrder !== undefined) {
          batchedUpdate.column_order = updates.columnOrder;
        }
        if (updates.columnRenameMapping !== undefined) {
          batchedUpdate.column_rename_mapping = updates.columnRenameMapping;
        }
        if (updates.columnTimeFormats !== undefined) {
          batchedUpdate.column_time_formats = updates.columnTimeFormats;
        }
        if (updates.columnListFormats !== undefined) {
          batchedUpdate.column_list_formats = updates.columnListFormats;
        }

        try {
          return await updateColumnConfig(batchedUpdate);
        } catch (err) {
          // If backend update fails, fall back to local storage
          console.warn(
            "Failed to update backend column config, falling back to local storage",
            err
          );
          // Fall through to local storage update
        }
      }

      // For local storage or on backend failure, update each one individually (synchronously)
      if (updates.columnVisibility !== undefined) {
        setLocalColumnVisibility(updates.columnVisibility);
      }
      if (updates.columnOrder !== undefined) {
        setLocalColumnOrder(updates.columnOrder);
      }
      if (updates.columnRenameMapping !== undefined) {
        setLocalColumnRenameMapping(updates.columnRenameMapping);
      }
      if (updates.columnTimeFormats !== undefined) {
        setLocalColumnTimeFormats(updates.columnTimeFormats);
      }
      if (updates.columnListFormats !== undefined) {
        setLocalColumnListFormats(updates.columnListFormats);
      }
      return Promise.resolve();
    },
    [
      shouldUseBackend,
      updateColumnConfig,
      setLocalColumnVisibility,
      setLocalColumnOrder,
      setLocalColumnRenameMapping,
      setLocalColumnTimeFormats,
      setLocalColumnListFormats,
      error,
    ]
  );

  // Individual update functions for backward compatibility
  const setColumnVisibility = useCallback(
    (visibility: VisibilityState) => {
      return updateMultipleColumnConfigs({ columnVisibility: visibility });
    },
    [updateMultipleColumnConfigs]
  );

  const setColumnOrder = useCallback(
    (order: ColumnOrderState) => {
      return updateMultipleColumnConfigs({ columnOrder: order });
    },
    [updateMultipleColumnConfigs]
  );

  const setColumnRenameMapping = useCallback(
    (mapping: ColumnRenameMapping) => {
      return updateMultipleColumnConfigs({ columnRenameMapping: mapping });
    },
    [updateMultipleColumnConfigs]
  );

  const setColumnTimeFormats = useCallback(
    (formats: Record<string, TimeFormatOption>) => {
      return updateMultipleColumnConfigs({ columnTimeFormats: formats });
    },
    [updateMultipleColumnConfigs]
  );

  const setColumnListFormats = useCallback(
    (formats: Record<string, ListFormatOption>) => {
      return updateMultipleColumnConfigs({ columnListFormats: formats });
    },
    [updateMultipleColumnConfigs]
  );

  return {
    columnVisibility,
    columnOrder,
    columnRenameMapping,
    columnTimeFormats,
    columnListFormats,
    setColumnVisibility,
    setColumnOrder,
    setColumnRenameMapping,
    setColumnTimeFormats,
    setColumnListFormats,
    updateMultipleColumnConfigs,
    isLoading,
    useBackend: shouldUseBackend && !error,
  };
};

export type UsePresetColumnStateValue = ReturnType<typeof usePresetColumnState>;
