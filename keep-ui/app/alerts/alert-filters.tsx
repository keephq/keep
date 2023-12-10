import { useState } from "react";
import { AlertDto } from "./models";
import CreatableSelect from "react-select/creatable";

export default function AlertFilters({
  alerts,
  selectedOptions,
  setSelectedOptions,
}: {
  alerts: AlertDto[];
  selectedOptions: any;
  setSelectedOptions: any;
}) {
  const uniqueKeys = Array.from(new Set(alerts.flatMap(Object.keys)));
  const options = uniqueKeys.map((key) => ({ value: key, label: key }));
  const handleChange = (selected: any) => {
    console.log(selected);
    setSelectedOptions(selected);
  };

  return (
    <CreatableSelect
      isMulti
      options={options as []}
      value={selectedOptions}
      onChange={handleChange}
    />
  );
}
