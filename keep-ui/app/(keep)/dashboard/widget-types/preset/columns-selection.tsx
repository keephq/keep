import { useI18n } from "@/i18n/hooks/useI18n";
import { useFacetPotentialFields } from "@/features/filter/hooks";
import { MultiSelect, MultiSelectItem } from "@tremor/react";
import React, { useEffect, useMemo, useState } from "react";
import { defaultColumns } from "./constants";

interface ColumnsSelectionProps {
  selectedColumns?: string[];
  onChange: (selected: string[]) => void;
}

const ColumnsSelection: React.FC<ColumnsSelectionProps> = ({
  selectedColumns,
  onChange,
}) => {
  const { t } = useI18n();
  const [selectedColumnsState, setSelectedColumnsState] = useState<Set<string>>(
    new Set(selectedColumns || defaultColumns)
  );
  const { data } = useFacetPotentialFields("alerts");

  useEffect(
    () => onChange(Array.from(selectedColumnsState)),
    [selectedColumnsState]
  );

  const sortedOptions = useMemo(() => {
    return data?.slice().sort((first, second) => {
      const inSetA = selectedColumnsState.has(first);
      const inSetB = selectedColumnsState.has(second);

      if (inSetA && !inSetB) return -1;
      if (!inSetA && inSetB) return 1;

      return first.localeCompare(second);
    });
  }, [data, selectedColumnsState]);

  return (
    <MultiSelect
      placeholder={t("dashboard.selectAlertColumns")}
      value={Array.from(selectedColumnsState)}
      onValueChange={(selected) => setSelectedColumnsState(new Set(selected))}
    >
      {sortedOptions?.map((field) => (
        <MultiSelectItem key={field} value={field}>
          {field}
        </MultiSelectItem>
      ))}
    </MultiSelect>
  );
};

export default ColumnsSelection;
