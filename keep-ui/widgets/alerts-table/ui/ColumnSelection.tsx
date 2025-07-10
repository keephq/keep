import React, { FormEvent, useState } from "react";
import { Table } from "@tanstack/table-core";
import { Button, TextInput } from "@tremor/react";
import { VisibilityState } from "@tanstack/react-table";
import { FiSearch } from "react-icons/fi";
import { AlertDto } from "@/entities/alerts/model";
import { usePresetColumnState } from "@/entities/presets/model";

interface AlertColumnsSelectProps {
  table: Table<AlertDto>;
  presetName: string;
  presetId?: string;
  onClose?: () => void;
}

export default function ColumnSelection({
  table,
  presetName,
  presetId,
  onClose,
}: AlertColumnsSelectProps) {
  const tableColumns = table.getAllColumns();

  // Use the unified column state hook - it will automatically determine
  // whether to use backend or local storage based on preset type
  const {
    columnVisibility,
    columnOrder,
    updateMultipleColumnConfigs,
    isLoading,
    useBackend,
  } = usePresetColumnState({
    presetName,
    presetId,
    useBackend: !!presetId, // Try to use backend if preset ID is available
  });

  const [searchTerm, setSearchTerm] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  // Local state to track checkbox changes before submission
  const [localColumnVisibility, setLocalColumnVisibility] =
    useState<VisibilityState>(columnVisibility);
  
  // Use a ref to track the previous columnVisibility to prevent infinite loops
  const prevColumnVisibilityRef = React.useRef<VisibilityState>(columnVisibility);

  // Update local state when backend state changes
  React.useEffect(() => {
    console.log('ColumnSelection: columnVisibility changed', {
      presetName,
      useBackend,
      columnVisibility,
      localColumnVisibility
    });
    
    // Only update if the columnVisibility has actually changed
    if (JSON.stringify(prevColumnVisibilityRef.current) !== JSON.stringify(columnVisibility)) {
      console.log('ColumnSelection: updating localColumnVisibility');
      setLocalColumnVisibility(columnVisibility);
      prevColumnVisibilityRef.current = columnVisibility;
    }
  }, [columnVisibility, presetName]);

  const columnsOptions = tableColumns
    .filter((col) => col.getIsPinned() === false)
    .map((col) => col.id);

  const filteredColumns = React.useMemo(() => {
    return columnsOptions.filter((column) =>
      column.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [columnsOptions, searchTerm]);

  // Handle search state - only set to false when search finishes
  React.useEffect(() => {
    if (isSearching) {
      setIsSearching(false);
    }
  }, [filteredColumns, isSearching]); // Only run when we're currently searching

  // Debug logging for e2e tests
  React.useEffect(() => {
    if (searchTerm) {
      console.log(`ColumnSelection: Searching for "${searchTerm}"`);
      console.log(`ColumnSelection: Available columns:`, columnsOptions);
      console.log(`ColumnSelection: Filtered columns:`, filteredColumns);
    }
  }, [searchTerm, columnsOptions, filteredColumns]);

  const handleSearchChange = (value: string) => {
    if (value) {
      setIsSearching(true);
    }
    setSearchTerm(value);
  };

  const handleCheckboxChange = (column: string, checked: boolean) => {
    console.log('ColumnSelection: handleCheckboxChange', {
      column,
      checked,
      currentLocalState: localColumnVisibility
    });
    
    setLocalColumnVisibility((prev) => {
      const newState = {
        ...prev,
        [column]: checked,
      };
      console.log('ColumnSelection: new local state', newState);
      return newState;
    });
  };

  const onMultiSelectChange = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    // Create a new order array with all existing columns and newly selected columns
    const selectedColumnIds = filteredColumns.filter(
      (column) => localColumnVisibility[column]
    );

    const updatedOrder = [
      ...columnOrder,
      ...selectedColumnIds.filter((id) => !columnOrder.includes(id)),
    ];

    // Remove any columns that are no longer selected
    const finalOrder = updatedOrder.filter(
      (id) => localColumnVisibility[id] || !filteredColumns.includes(id)
    );

    try {
      // Use batched update to avoid multiple API calls and toasts
      await updateMultipleColumnConfigs({
        columnVisibility: localColumnVisibility,
        columnOrder: finalOrder,
      });
      onClose?.();
    } catch (error) {
      console.error("Failed to save column configuration:", error);
      // Don't close on error, let user try again
    }
  };

  return (
    <form onSubmit={onMultiSelectChange} className="flex flex-col h-full">
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <span className="text-gray-400 text-sm">Set table fields</span>
          {useBackend && (
            <span className="text-xs text-green-600 bg-green-100 px-2 py-1 rounded">
              Synced across devices
            </span>
          )}
        </div>
        <TextInput
          icon={FiSearch}
          placeholder="Search fields..."
          value={searchTerm}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="mb-3"
        />
        <div className="flex-1 overflow-y-auto max-h-[350px]">
          {isLoading && useBackend ? (
            <div className="flex items-center justify-center py-8 text-gray-400">
              <span data-testid="columns-loading">
                Loading column configuration...
              </span>
            </div>
          ) : isSearching ? (
            <div className="flex items-center justify-center py-8 text-gray-400">
              <span data-testid="columns-searching">Searching...</span>
            </div>
          ) : (
            <ul
              className="space-y-1"
              data-testid="column-list"
              data-column-count={filteredColumns.length}
            >
              {filteredColumns.map((column) => (
                <li key={column}>
                  <label className="cursor-pointer p-2 flex items-center">
                    <input
                      className="mr-2"
                      name={column}
                      type="checkbox"
                      checked={localColumnVisibility[column] || false}
                      onChange={(e) =>
                        handleCheckboxChange(column, e.target.checked)
                      }
                      data-testid={`column-checkbox-${column}`}
                      data-checked={localColumnVisibility[column] || false}
                    />
                    {column}
                  </label>
                </li>
              ))}
              {filteredColumns.length === 0 && (
                <li
                  className="text-gray-400 p-2"
                  data-testid="no-columns-found"
                >
                  No columns found matching &ldquo;{searchTerm}&rdquo;
                </li>
              )}
            </ul>
          )}
        </div>
      </div>
      <Button
        className="mt-4"
        color="orange"
        type="submit"
        loading={useBackend && isLoading}
        disabled={useBackend && isLoading}
      >
        {useBackend && isLoading ? "Saving..." : "Save changes"}
      </Button>
    </form>
  );
}
