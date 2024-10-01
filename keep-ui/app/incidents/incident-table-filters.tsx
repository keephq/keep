import type { FC } from "react";
import { MultiSelect, MultiSelectItem } from "@tremor/react";
import {useIncidentFilterContext} from "./incident-table-filters-context";

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
  } = useIncidentFilterContext()


  return (
    <div className="flex">

      <MultiSelect
        onValueChange={setStatuses}
        value={statuses}
        placeholder="Filter by status..."
        className="w-full ml-2.5"
        // icon={TagIcon}
      >
        {meta?.statuses.map((value) => (
          <MultiSelectItem key={value} value={value}>{value}</MultiSelectItem>
        ))}
      </MultiSelect>

      <MultiSelect
        onValueChange={setSeverities}
        value={severities}
        placeholder="Filter by severity..."
        className="w-full ml-2.5"
        // icon={TagIcon}
      >
        {meta?.severities.map((value) => (
          <MultiSelectItem key={value} value={value}>{value}</MultiSelectItem>
        ))}
      </MultiSelect>

      <MultiSelect
        onValueChange={setAssignees}
        value={assignees}
        placeholder="Filter by assinee..."
        className="w-full ml-2.5"
        // icon={TagIcon}
      >
        {meta?.assignees.map((value) => (
          <MultiSelectItem key={value} value={value}>{value}</MultiSelectItem>
        ))}
      </MultiSelect>

      <MultiSelect
        onValueChange={setServices}
        value={services}
        placeholder="Filter by service..."
        className="w-full ml-2.5"
        // icon={TagIcon}
      >
        {meta?.services.map((value) => (
          <MultiSelectItem key={value} value={value}>{value}</MultiSelectItem>
        ))}
      </MultiSelect>

      <MultiSelect
        onValueChange={setSources}
        value={sources}
        placeholder="Filter by source..."
        className="w-full ml-2.5"
        // icon={TagIcon}
      >
        {meta?.sources.map((value) => (
          <MultiSelectItem key={value} value={value}>{value}</MultiSelectItem>
        ))}
      </MultiSelect>


    </div>
  )
}