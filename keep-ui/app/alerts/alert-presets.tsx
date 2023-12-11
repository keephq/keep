import { useState, useEffect, useRef } from "react";
import { Dispatch, SetStateAction } from "react";
import { AlertDto, Preset } from "./models";
import CreatableSelect from "react-select/creatable";
import { GroupBase, OptionsOrGroups } from "react-select/dist/declarations/src";
import { Button } from "@tremor/react";
import { CheckIcon, PlusIcon, TrashIcon } from "@radix-ui/react-icons";
import { getApiURL } from "utils/apiUrl";
import { toast } from "react-toastify";

export interface Option {
  readonly label: string;
  readonly value: string;
}

export default function AlertPresets({
  preset,
  alerts,
  selectedOptions,
  accessToken,
  setSelectedOptions,
  presetsMutator,
}: {
  preset: Preset | null;
  alerts: AlertDto[];
  selectedOptions: Option[];
  setSelectedOptions: Dispatch<SetStateAction<Option[]>>;
  accessToken: string;
  presetsMutator: () => void;
}) {
  const apiUrl = getApiURL();
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
      handleInputChange(`${actionMeta.option.value}=`);
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

  async function deletePreset(presetId: string) {
    if (
      confirm(`You are about to delete preset ${preset!.name}, are you sure?`)
    ) {
      const response = await fetch(`${apiUrl}/preset/${presetId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (response.ok) {
        toast(`Preset ${preset!.name} deleted!`, {
          position: "top-left",
          type: "success",
        });
        presetsMutator();
      }
    }
  }

  async function addOrUpdatePreset() {
    const presetName = prompt(
      `${preset?.name ? "Update preset name?" : "Enter new preset name"}`,
      preset?.name === "Feed" || preset?.name === "Deleted" ? "" : preset?.name
    );
    if (presetName) {
      const options = selectedOptions.map((option) => {
        return {
          value: option.value,
          label: option.label,
        };
      });
      const response = await fetch(
        preset?.id ? `${apiUrl}/preset/${preset?.id}` : `${apiUrl}/preset`,
        {
          method: preset?.id ? "PUT" : "POST",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ name: presetName, options: options }),
        }
      );
      if (response.ok) {
        toast(
          preset?.name
            ? `Preset ${presetName} updated!`
            : `Preset ${presetName} created!`,
          {
            position: "top-left",
            type: "success",
          }
        );
        presetsMutator();
      }
    }
  }

  return (
    <div className="flex w-full">
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
        className="w-full"
      />
      {preset?.name === "Feed" && (
        <Button
          icon={PlusIcon}
          size="xs"
          color="orange"
          title="Create preset"
          className="ml-2.5"
          disabled={selectedOptions.length <= 0}
          onClick={async () => await addOrUpdatePreset()}
        />
      )}
      {preset?.name !== "Deleted" && preset?.name !== "Feed" && (
        <div className="flex ml-2.5">
          <Button
            icon={CheckIcon}
            size="xs"
            color="orange"
            title="Save preset"
            className="mr-1"
            disabled={selectedOptions.length <= 0}
            onClick={async () => await addOrUpdatePreset()}
          />
          <Button
            icon={TrashIcon}
            size="xs"
            color="orange"
            variant="secondary"
            title="Delete preset"
            onClick={async () => {
              await deletePreset(preset!.id!);
            }}
          />
        </div>
      )}
    </div>
  );
}
