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
import { STATIC_PRESETS_NAMES } from "./constants";
import { ColumnConfiguration } from "./types";

interface UsePresetColumnStateOptions {
  presetName: string;
  presetId?: string;
  useBackend?: boolean; // Flag to enable backend usage
}

// Static preset IDs that should always use local storage
const STATIC_PRESET_IDS = [
  "11111111-1111-1111-1111-111111111111", // FEED_PRESET_ID
  "11111111-1111-1111-1111-111111111113", // DISMISSED_PRESET_ID
  "11111111-1111-1111-1111-111111111114", // GROUPS_PRESET_ID
  "11111111-1111-1111-1111-111111111115", // WITHOUT_INCIDENT_PRESET_ID
];

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
  const shouldUseBackend = useBackend && !isStaticPreset;

  // Backend-based state
  const { columnConfig, updateColumnConfig, isLoading } = usePresetColumnConfig(
    {
      presetId: shouldUseBackend ? presetId : undefined,
    }
  );

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

  // Determine which state to use
  const columnVisibility = useMemo(() => {
    if (
      shouldUseBackend &&
      columnConfig.column_visibility &&
      Object.keys(columnConfig.column_visibility).length > 0
    ) {
      return columnConfig.column_visibility;
    }
    return localColumnVisibility;
  }, [shouldUseBackend, columnConfig.column_visibility, localColumnVisibility]);

  const columnOrder = useMemo(() => {
    if (
      shouldUseBackend &&
      columnConfig.column_order &&
      columnConfig.column_order.length > 0
    ) {
      return columnConfig.column_order;
    }
    return localColumnOrder;
  }, [shouldUseBackend, columnConfig.column_order, localColumnOrder]);

  const columnRenameMapping = useMemo(() => {
    if (shouldUseBackend && columnConfig.column_rename_mapping) {
      return columnConfig.column_rename_mapping;
    }
    return localColumnRenameMapping;
  }, [
    shouldUseBackend,
    columnConfig.column_rename_mapping,
    localColumnRenameMapping,
  ]);

  const columnTimeFormats = useMemo(() => {
    if (shouldUseBackend && columnConfig.column_time_formats) {
      return columnConfig.column_time_formats as Record<
        string,
        TimeFormatOption
      >;
    }
    return localColumnTimeFormats;
  }, [
    shouldUseBackend,
    columnConfig.column_time_formats,
    localColumnTimeFormats,
  ]);

  const columnListFormats = useMemo(() => {
    if (shouldUseBackend && columnConfig.column_list_formats) {
      return columnConfig.column_list_formats as Record<
        string,
        ListFormatOption
      >;
    }
    return localColumnListFormats;
  }, [
    shouldUseBackend,
    columnConfig.column_list_formats,
    localColumnListFormats,
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
      if (shouldUseBackend) {
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

        return updateColumnConfig(batchedUpdate);
      } else {
        // For local storage, update each one individually (synchronously)
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
      }
    },
    [
      shouldUseBackend,
      updateColumnConfig,
      setLocalColumnVisibility,
      setLocalColumnOrder,
      setLocalColumnRenameMapping,
      setLocalColumnTimeFormats,
      setLocalColumnListFormats,
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
    useBackend: shouldUseBackend,
  };
};

export type UsePresetColumnStateValue = ReturnType<typeof usePresetColumnState>;
