import { useLocalStorage } from "utils/hooks/useLocalStorage";

/**
 * Hook to manage expanded rows in alert tables
 * Stores the expanded state in localStorage to persist across sessions
 */
export function useExpandedRows(presetName: string) {
  // Normalize the presetName to lowercase to ensure consistency regardless of case
  const normalizedPresetName = presetName.toLowerCase();

  const [expandedRows, setExpandedRows] = useLocalStorage<
    Record<string, boolean>
  >(`expanded-rows-${normalizedPresetName}`, {});

  const toggleRowExpanded = (fingerprint: string) => {
    setExpandedRows((prev) => ({
      ...prev,
      [fingerprint]: !prev[fingerprint],
    }));
  };

  const isRowExpanded = (fingerprint: string): boolean => {
    return !!expandedRows[fingerprint];
  };

  // New property to check if any row is expanded
  const anyRowExpanded = Object.values(expandedRows).some(Boolean);

  return {
    expandedRows,
    toggleRowExpanded,
    isRowExpanded,
    anyRowExpanded,
  };
}
