import { useState, useEffect, useRef, useMemo } from "react";
import { Dispatch, SetStateAction } from "react";
import { AlertDto, Preset } from "./models";
import CreatableSelect from "react-select/creatable";
import { Button, Subtitle, Switch } from "@tremor/react";
import { CheckIcon, PlusIcon, TrashIcon } from "@radix-ui/react-icons";
import { getApiURL } from "utils/apiUrl";
import { toast } from "react-toastify";
import { useSession } from "next-auth/react";
import { usePresets } from "utils/hooks/usePresets";
import { useRouter } from "next/navigation";

export interface Option {
  readonly label: string;
  readonly value: string;
}

interface Props {
  preset: Preset | null;
  alerts: AlertDto[];
  selectedOptions: Option[];
  setSelectedOptions: Dispatch<SetStateAction<Option[]>>;
  isLoading: boolean;
}

export default function AlertPresets({
  preset,
  alerts,
  selectedOptions,
  setSelectedOptions,
  isLoading,
}: Props) {
  const [isPrivate, setIsPrivate] = useState<boolean>(false);

  const handleSwitchChange = (value: boolean) => {
    setIsPrivate(value);
  }
  const apiUrl = getApiURL();
  const { useAllPresets } = usePresets();
  const { mutate: presetsMutator } = useAllPresets({
    revalidateOnFocus: false,
  });
  const { data: session } = useSession();
  const router = useRouter();

  const selectRef = useRef(null);
  const [options, setOptions] = useState<Option[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const uniqueValuesMap = useMemo(() => {
    const newUniqueValuesMap = new Map<string, Set<string>>();
    if (alerts) {
      // Populating the map with keys and values
      alerts.forEach((alert) => {
        Object.entries(alert).forEach(([key, value]) => {
          if (typeof value !== "string" && key !== "source") return;
          if (!newUniqueValuesMap.has(key)) {
            newUniqueValuesMap.set(key, new Set());
          }
          if (key === "source") {
            value = value?.join(",");
          }
          if (!newUniqueValuesMap.get(key)?.has(value?.trim()))
            newUniqueValuesMap.get(key)?.add(value?.toString().trim());
        });
      });
    }
    return newUniqueValuesMap;
  }, [alerts]);

  // Initially, set options to keys
  useEffect(() => {
    setOptions(
      Array.from(uniqueValuesMap.keys()).map((key) => ({
        label: key,
        value: key,
      }))
    );
  }, [uniqueValuesMap]);

  const isValidNewOption = () => {
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
      setIsMenuOpen(false);
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

  // When deleting a preset, we check if it is a private or global
  async function deletePreset(presetId: string) {
    if (
      confirm(`You are about to delete preset ${preset!.name}, are you sure?`)
    ) {
      const response = await fetch(`${apiUrl}/preset/${presetId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
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


  // Add an option or check box, if it will be global or private.
  async function addOrUpdatePreset() {
    const newPresetName = prompt(
      `${preset?.name ? "Update preset name?" : "Enter new preset name"}`,
      preset?.name === "feed" || preset?.name === "deleted" ? "" : preset?.name
    );
    if (newPresetName) {
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
            Authorization: `Bearer ${session?.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: newPresetName,
            options: options,
            is_private: isPrivate,
          }),
        }
      );
      if (response.ok) {
        toast(
          preset?.name
            ? `Preset ${newPresetName} updated!`
            : `Preset ${newPresetName} created!`,
          {
            position: "top-left",
            type: "success",
          }
        );
        await presetsMutator();
        router.push(`/alerts/${newPresetName.toLowerCase()}`);
      }
    }
  }

  return (
    <>
      <Subtitle>Filters</Subtitle>
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
          menuIsOpen={isMenuOpen}
          onFocus={() => setIsMenuOpen(true)}
          onBlur={() => setIsMenuOpen(false)}
          isClearable={false}
          isDisabled={isLoading}
        />

{preset?.name === "feed" && (
          <>
<div className="flex items-center mb-4">
           
           <Button 
  icon={PlusIcon} 
  size="xs" 
  color="orange" 
  className="ml-2.5 rounded-lg shadow-md"
  disabled={selectedOptions.length <= 0}
  onClick={async () => await addOrUpdatePreset()}
  tooltip="Save current filter as a view"
>
  Create Preset
</Button>
  <Switch 
    id="switch"
    name="switch"
    checked={isPrivate}
    onChange={handleSwitchChange} 
    className="focus:outline-none focus:ring-2 focus:ring-orange-500"
  />

  <label 
    htmlFor="switch"
    className="text-gray-700 dark:text-gray-200 ml-2 text-sm font-medium"
  >
    Save preset as private or global.
  </label>  
</div>
          </>)}
        {preset?.name !== "deleted" && preset?.name !== "feed" && (
          <div className="flex ml-2.5">
            <Button
              icon={CheckIcon}
              size="xs"
              color="orange"
              title="Save preset"
              className="mr-1"
              disabled={selectedOptions.length <= 0}
              onClick={async () => await addOrUpdatePreset()}
            >
              Save Preset
            </Button>
            <Button
              icon={TrashIcon}
              size="xs"
              color="orange"
              variant="secondary"
              title="Delete preset"
              onClick={async () => {
                await deletePreset(preset!.id!);
              }}
            >
              Delete Preset
            </Button>
          </div>
        )}
      </div>
    </>
  );
}