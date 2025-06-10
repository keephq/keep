import { useCallback, useMemo } from "react";
import { VisibilityState, ColumnOrderState } from "@tanstack/react-table";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { usePresetColumnConfig } from "./usePresetColumnConfig";
import { TimeFormatOption } from "@/widgets/alerts-table/lib/alert-table-time-format";
import { ListFormatOption } from "@/widgets/alerts-table/lib/alert-table-list-format";
import { ColumnRenameMapping } from "@/widgets/alerts-table/ui/alert-table-column-rename";
import { DEFAULT_COLS, DEFAULT_COLS_VISIBILITY } from "@/widgets/alerts-table/lib/alert-table-utils";
import { usePresets } from "./usePresets";

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
  // Backend-based state
  const { columnConfig, updateColumnConfig, isLoading } = usePresetColumnConfig({
    presetId: useBackend ? presetId : undefined
  });

  // Local storage fallbacks (existing implementation)
  const [localColumnVisibility, setLocalColumnVisibility] = useLocalStorage<VisibilityState>(
    `column-visibility-${presetName}`,
    DEFAULT_COLS_VISIBILITY
  );

  const [localColumnOrder, setLocalColumnOrder] = useLocalStorage<ColumnOrderState>(
    `column-order-${presetName}`,
    DEFAULT_COLS
  );

  const [localColumnRenameMapping, setLocalColumnRenameMapping] = useLocalStorage<ColumnRenameMapping>(
    `column-rename-mapping-${presetName}`,
    {}
  );

  const [localColumnTimeFormats, setLocalColumnTimeFormats] = useLocalStorage<Record<string, TimeFormatOption>>(
    `column-time-formats-${presetName}`,
    {}
  );

  const [localColumnListFormats, setLocalColumnListFormats] = useLocalStorage<Record<string, ListFormatOption>>(
    `column-list-formats-${presetName}`,
    {}
  );

  // Determine which state to use
  const columnVisibility = useMemo(() => {
    if (useBackend && columnConfig.column_visibility && Object.keys(columnConfig.column_visibility).length > 0) {
      return columnConfig.column_visibility;
    }
    return localColumnVisibility;
  }, [useBackend, columnConfig.column_visibility, localColumnVisibility]);

  const columnOrder = useMemo(() => {
    if (useBackend && columnConfig.column_order && columnConfig.column_order.length > 0) {
      return columnConfig.column_order;
    }
    return localColumnOrder;
  }, [useBackend, columnConfig.column_order, localColumnOrder]);

  const columnRenameMapping = useMemo(() => {
    if (useBackend && columnConfig.column_rename_mapping) {
      return columnConfig.column_rename_mapping;
    }
    return localColumnRenameMapping;
  }, [useBackend, columnConfig.column_rename_mapping, localColumnRenameMapping]);

  const columnTimeFormats = useMemo(() => {
    if (useBackend && columnConfig.column_time_formats) {
      return columnConfig.column_time_formats as Record<string, TimeFormatOption>;
    }
    return localColumnTimeFormats;
  }, [useBackend, columnConfig.column_time_formats, localColumnTimeFormats]);

  const columnListFormats = useMemo(() => {
    if (useBackend && columnConfig.column_list_formats) {
      return columnConfig.column_list_formats as Record<string, ListFormatOption>;
    }
    return localColumnListFormats;
  }, [useBackend, columnConfig.column_list_formats, localColumnListFormats]);

  // Update functions
  const setColumnVisibility = useCallback(
    async (visibility: VisibilityState) => {
      if (useBackend) {
        await updateColumnConfig({ column_visibility: visibility });
      } else {
        setLocalColumnVisibility(visibility);
      }
    },
    [useBackend, updateColumnConfig, setLocalColumnVisibility]
  );

  const setColumnOrder = useCallback(
    async (order: ColumnOrderState) => {
      if (useBackend) {
        await updateColumnConfig({ column_order: order });
      } else {
        setLocalColumnOrder(order);
      }
    },
    [useBackend, updateColumnConfig, setLocalColumnOrder]
  );

  const setColumnRenameMapping = useCallback(
    async (mapping: ColumnRenameMapping) => {
      if (useBackend) {
        await updateColumnConfig({ column_rename_mapping: mapping });
      } else {
        setLocalColumnRenameMapping(mapping);
      }
    },
    [useBackend, updateColumnConfig, setLocalColumnRenameMapping]
  );

  const setColumnTimeFormats = useCallback(
    async (formats: Record<string, TimeFormatOption>) => {
      if (useBackend) {
        await updateColumnConfig({ column_time_formats: formats });
      } else {
        setLocalColumnTimeFormats(formats);
      }
    },
    [useBackend, updateColumnConfig, setLocalColumnTimeFormats]
  );

  const setColumnListFormats = useCallback(
    async (formats: Record<string, ListFormatOption>) => {
      if (useBackend) {
        await updateColumnConfig({ column_list_formats: formats });
      } else {
        setLocalColumnListFormats(formats);
      }
    },
    [useBackend, updateColumnConfig, setLocalColumnListFormats]
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
    isLoading,
    useBackend,
  };
};

export type UsePresetColumnStateValue = ReturnType<typeof usePresetColumnState>;