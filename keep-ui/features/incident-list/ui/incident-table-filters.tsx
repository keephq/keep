import type { FC } from "react";
import { MultiSelect, MultiSelectItem } from "@tremor/react";
import { useIncidentFilterContext } from "./incident-table-filters-context";
import { capitalize } from "@/utils/helpers";

export const IncidentTableFilters: FC = (props) => {
  const {
    meta,
    statuses,
    severities,
    assignees,
    services,
    sources,
    setStatuses,
    setSeverities,
    setAssignees,
    setServices,
    setSources,
  } = useIncidentFilterContext();

  return (
    <div className="flex flex-col md:flex-row gap-2">
      {/* TODO: use copy-and-paste multiselect component to be able to control the width */}
      <MultiSelect
        onValueChange={setStatuses}
        value={statuses}
        placeholder="Status"
      >
        {meta?.statuses.map((value) => (
          <MultiSelectItem key={value} value={value}>
            {capitalize(value)}
          </MultiSelectItem>
        ))}
      </MultiSelect>

      <MultiSelect
        onValueChange={setSeverities}
        value={severities}
        placeholder="Severity"
      >
        {meta?.severities.map((value) => (
          <MultiSelectItem key={value} value={value}>
            {capitalize(value)}
          </MultiSelectItem>
        ))}
      </MultiSelect>

      <MultiSelect
        onValueChange={setAssignees}
        value={assignees}
        placeholder="Assignee"
      >
        {meta?.assignees.map((value) => (
          <MultiSelectItem key={value} value={value}>
            {capitalize(value)}
          </MultiSelectItem>
        ))}
      </MultiSelect>

      <MultiSelect
        onValueChange={setServices}
        value={services}
        placeholder="Service"
      >
        {meta?.services.map((value) => (
          <MultiSelectItem key={value} value={value}>
            {capitalize(value)}
          </MultiSelectItem>
        ))}
      </MultiSelect>

      <MultiSelect
        onValueChange={setSources}
        value={sources}
        placeholder="Source"
      >
        {meta?.sources.map((value) => (
          <MultiSelectItem key={value} value={value}>
            {capitalize(value)}
          </MultiSelectItem>
        ))}
      </MultiSelect>
    </div>
  );
};
