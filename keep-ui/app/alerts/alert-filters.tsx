import { useState, useEffect, useRef } from "react";
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
  const selectRef = useRef(null);
  const [inputValue, setInputValue] = useState("");
  const uniqueValuesMap = new Map<string, Set<string>>();

  // Populating the map with keys and values
  alerts.forEach((alert) => {
    Object.entries(alert).forEach(([key, value]) => {
      if (typeof value !== "string") return;
      if (!uniqueValuesMap.has(key)) {
        uniqueValuesMap.set(key, new Set());
      }
      if (!uniqueValuesMap.get(key)?.has(value?.trim()))
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

    if (event.key === "Enter") {
      if (!inputElement.value.includes("=")) {
        event.preventDefault();
      }
    }

    if (event.key === "Tab") {
      event.preventDefault();
      // Only add to selectedOptions if focusedOption is not null
      const select = selectRef.current as any;
      if (select?.state.focusedOption) {
        const value = select.state.focusedOption.value;
        if (value.includes("=")) {
          handleInputChange(select.state.focusedOption.value);
        } else {
          handleInputChange(`${value}=`);
        }
      }
    }
  };

  const handleChange = (selected: any, actionMeta: any) => {
    if (
      actionMeta.action === "select-option" &&
      selected.some((option: any) => !option.value.includes("="))
    ) {
      // Handle invalid option selection
      handleInputChange(`${selected[0].value}=`);
      // Optionally, you can prevent the selection or handle it differently
    } else {
      setSelectedOptions(selected);
    }
  };

  const handleInputChange = (inputValue: string) => {
    setInputValue(inputValue);
    if (inputValue.includes("=")) {
      const [inputKey, inputValuePart] = inputValue.split("=");
      if (uniqueValuesMap.has(inputKey)) {
        const filteredValues = Array.from(
          uniqueValuesMap.get(inputKey) || []
        ).filter((value) => value?.startsWith(inputValuePart));
        const newOptions = filteredValues.map((value) => ({
          label: `${inputKey}=${value}`,
          value: `${inputKey}=${value}`,
        }));
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
      inputValue={inputValue}
      filterOption={filterOption}
      onKeyDown={handleKeyDown}
      isValidNewOption={isValidNewOption}
      ref={selectRef}
    />
  );
}
