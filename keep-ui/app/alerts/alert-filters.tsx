import { useState, useEffect } from "react";
import { Dispatch, SetStateAction } from "react";
import { AlertDto } from "./models";
import CreatableSelect from "react-select/creatable";
import { GroupBase, OptionsOrGroups } from "react-select/dist/declarations/src";

export interface Option {
  readonly label: string;
  readonly value: string;
}

export default function AlertFilters({
  alerts,
  selectedOptions,
  setSelectedOptions,
}: {
  alerts: AlertDto[];
  selectedOptions: Option[];
  setSelectedOptions: Dispatch<SetStateAction<Option[]>>;
}) {
  const [options, setOptions] = useState<Option[]>([]);
  const uniqueValuesMap = new Map<string, Set<string>>();

  // Populating the map with keys and values
  alerts.forEach((alert) => {
    Object.entries(alert).forEach(([key, value]) => {
      if (!uniqueValuesMap.has(key)) {
        uniqueValuesMap.set(key, new Set());
      }
      if (!uniqueValuesMap.get(key)?.has(value?.toString().trim()))
        uniqueValuesMap.get(key)?.add(value?.toString().trim());
    });
  });

  // Initially, set options to keys
  useEffect(() => {
    setOptions(
      Array.from(uniqueValuesMap.keys()).map((key) => ({
        label: key,
        value: key,
      }))
    );
  }, [alerts]);

  const isValidNewOption = (
    inputValue: string,
    selectValue: OptionsOrGroups<Option, GroupBase<Option>>,
    selectOptions: OptionsOrGroups<Option, GroupBase<Option>>,
    accessors: {
      getOptionValue: (option: Option) => string;
      getOptionLabel: (option: Option) => string;
    }
  ) => {
    // Only allow creating new options if the input includes '='
    return inputValue.includes("=");
  };
  // Handler for key down events
  const handleKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    const inputElement = event.target as HTMLInputElement; // Cast to HTMLInputElement

    if (event.key === "Enter" || event.key === "Tab") {
      if (!inputElement.value.includes("=")) {
        event.preventDefault();
      }
    }
  };

  const handleChange = (selected: any) => {
    setSelectedOptions(selected);
  };

  const handleInputChange = (inputValue: string) => {
    if (inputValue.includes("=")) {
      const [inputKey, inputValuePart] = inputValue.split("=");
      if (uniqueValuesMap.has(inputKey)) {
        const filteredValues = Array.from(
          uniqueValuesMap.get(inputKey) || []
        ).filter((value) => value.startsWith(inputValuePart));
        const newOptions = filteredValues.map((value) => ({
          label: `${inputKey}=${value}`,
          value: `${inputKey}=${value}`,
        }));
        console.log(newOptions);
        setOptions(newOptions);
      } else {
        setOptions([]);
      }
    } else {
      setOptions(
        Array.from(uniqueValuesMap.keys()).map((key) => ({
          label: key,
          value: key,
        }))
      );
    }
  };

  const filterOption = ({ label }: Option, input: string) => {
    return label.toLowerCase().includes(input.toLowerCase());
  };

  return (
    <CreatableSelect
      isMulti
      options={options}
      value={selectedOptions}
      onChange={handleChange}
      onInputChange={handleInputChange}
      filterOption={filterOption}
      onKeyDown={handleKeyDown}
      isValidNewOption={isValidNewOption}
    />
  );
}
