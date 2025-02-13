"use client";

import { InformationCircleIcon } from "@heroicons/react/24/outline";
import {
  NumberInput,
  TextInput,
  Textarea,
  Divider,
  Subtitle,
  Text,
  Badge,
  Button,
  Icon,
  TabGroup,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  MultiSelect,
  MultiSelectItem,
} from "@tremor/react";
import {
  ChangeEvent,
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { usePapaParse } from "react-papaparse";
import { toast } from "react-toastify";
import { useMappings } from "utils/hooks/useMappingRules";
import { MappingRule } from "./models";
import { useTopology } from "@/app/(keep)/topology/model";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast, Input } from "@/shared/ui";
import { PlusIcon, MinusIcon } from "@heroicons/react/20/solid";

interface Props {
  editRule: MappingRule | null;
  editCallback: (rule: MappingRule | null) => void;
}

export default function CreateOrEditMapping({ editRule, editCallback }: Props) {
  const api = useApi();
  const { mutate } = useMappings();
  const [tabIndex, setTabIndex] = useState<number>(0);
  const [mapName, setMapName] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");
  const [attributeGroups, setAttributeGroups] = useState<string[][]>([[]]);
  const [mappingType, setMappingType] = useState<"csv" | "topology">("csv");
  const [mapDescription, setMapDescription] = useState<string>("");
  const { topologyData } = useTopology();
  const [priority, setPriority] = useState<number>(0);
  const editMode = editRule !== null;
  const inputFile = useRef<HTMLInputElement>(null);

  // This useEffect runs whenever an `Edit` button is pressed in the table, and populates the form with the mapping data that needs to be edited.
  useEffect(() => {
    if (editRule !== null) {
      handleFileReset();
      setMapName(editRule.name);
      setFileName(editRule.file_name ? editRule.file_name : "");
      setMapDescription(editRule.description ? editRule.description : "");
      setMappingType(editRule.type ? editRule.type : "csv");
      setTabIndex(editRule.type === "csv" ? 0 : 1);
      setAttributeGroups(editRule.matchers ?? [[]]);
      setPriority(editRule.priority);
    }
  }, [editRule]);

  /** This is everything related with the uploaded CSV file */
  const [parsedData, setParsedData] = useState<any[] | null>(null);
  const attributes = useMemo(() => {
    if (parsedData) {
      return Object.keys(parsedData[0]);
    }

    // If we are in the editMode then we need to generate attributes i.e. [selectedAttributes + matchers]
    if (editRule) {
      return Object.keys(editRule.rows[0]);
    }
    return [];
  }, [parsedData, editRule]);
  const { readString } = usePapaParse();

  const handleFileReset = () => {
    if (inputFile.current) {
      inputFile.current.value = "";
    }
  };

  const updateMappingType = (index: number) => {
    setTabIndex(index);
    if (index === 0) {
      setParsedData(null);
      setMappingType("csv");
      setAttributeGroups([[]]);
    } else {
      setParsedData(topologyData!);
      setMappingType("topology");
      setAttributeGroups([["service"]]);
    }
  };

  const readFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    setFileName(file?.name || "");
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result;
      if (typeof text === "string") {
        readString(text, {
          header: true,
          complete: (results) => {
            if (results.data.length > 0) setParsedData(results.data);
          },
        });
      }
    };
    if (file) reader.readAsText(file);
  };

  const clearForm = () => {
    setMapName("");
    setMapDescription("");
    setParsedData(null);
    setAttributeGroups([[]]);
    handleFileReset();
  };

  const addRule = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.post("/mapping", {
        priority: priority,
        name: mapName,
        description: mapDescription,
        file_name: fileName,
        type: mappingType,
        matchers: attributeGroups,
        rows: mappingType === "csv" ? parsedData : null,
      });
      exitEditOrCreateMode();
      mutate();
      toast.success("Mapping created successfully");
    } catch (error) {
      showErrorToast(error, "Failed to create mapping");
    }
  };

  // This is the function that will be called on submitting the form in the editMode, it sends a PUT request to the backennd.
  const updateRule = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.put(`/mapping/${editRule?.id}`, {
        id: editRule?.id,
        priority: priority,
        name: mapName,
        description: mapDescription,
        file_name: fileName,
        type: mappingType,
        matchers: attributeGroups,
        rows: mappingType === "csv" ? parsedData : null,
      });
      exitEditOrCreateMode();
      mutate();
      toast.success("Mapping updated successfully");
    } catch (error) {
      showErrorToast(error, "Failed to update mapping");
    }
  };

  const exitEditOrCreateMode = () => {
    editCallback(null);
    clearForm();
  };

  useEffect(() => {
    if (mappingType === "topology") {
      setAttributeGroups([["service"]]);
    }
  }, [mappingType]);

  const handleAttributeChange = (groupIndex: number, selected: string[]) => {
    const newGroups = [...attributeGroups];
    newGroups[groupIndex] = selected;
    setAttributeGroups(newGroups);
  };

  const addAttributeGroup = () => {
    setAttributeGroups([...attributeGroups, []]);
  };

  const removeAttributeGroup = (index: number) => {
    setAttributeGroups(attributeGroups.filter((_, i) => i !== index));
  };

  return (
    <form
      className="w-full py-2 h-full overflow-y-auto"
      onSubmit={editMode ? updateRule : addRule}
    >
      <div className="mt-2.5 flex space-x-4 items-center">
        <div className="flex-1">
          <Text>
            Name<span className="text-red-500 text-xs">*</span>
          </Text>
          <TextInput
            placeholder="Map Name"
            required={true}
            value={mapName}
            onValueChange={setMapName}
          />
        </div>
        <div className="flex-1/5">
          <Text>
            Priority
            <Icon
              icon={InformationCircleIcon}
              size="xs"
              color="gray"
              tooltip="Higher priority will be executed first"
            />
          </Text>
          <NumberInput
            placeholder="Priority"
            required={true}
            value={priority}
            onValueChange={setPriority}
            min={0}
            max={100}
          />
        </div>
      </div>
      <div className="mt-2.5">
        <Text>Description</Text>
        <Textarea
          placeholder="Map Description"
          value={mapDescription}
          onValueChange={setMapDescription}
        />
      </div>
      <Divider />
      <div>
        <TabGroup
          index={tabIndex}
          onIndexChange={(index) => updateMappingType(index)}
        >
          <TabList>
            <Tab>CSV</Tab>
            <Tab
              disabled={!topologyData || topologyData.length === 0}
              className={`${
                !topologyData || topologyData.length === 0
                  ? "text-gray-400"
                  : ""
              }`}
            >
              Topology
            </Tab>
          </TabList>
          <TabPanels>
            <TabPanel>
              {mappingType === "csv" && (
                <Input
                  type="file"
                  accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
                  onChange={readFile}
                  required={!editMode}
                  ref={inputFile}
                />
              )}
              {!parsedData && (
                <Text className="text-xs text-red-500">
                  {!editMode ? "* Upload a CSV file to begin" : ""}
                </Text>
              )}
            </TabPanel>
            <TabPanel></TabPanel>
          </TabPanels>
        </TabGroup>
      </div>
      <Subtitle className="mt-2.5">Mapping Configuration</Subtitle>
      <div className="mt-2.5">
        If alert will match the atributes, it will be enriched with the rest of
        the fields{" "}
        {mappingType === "csv"
          ? "from matched row in the CVS."
          : "from matching node in the topology."}
        <div className="flex flex-col gap-4 mt-2">
          {attributeGroups.map((group, index) => (
            <div key={index} className="flex items-center space-x-2">
              <MultiSelect
                onValueChange={(selected) =>
                  handleAttributeChange(index, selected)
                }
                value={group}
                placeholder="Select Attributes"
                className="max-w-96"
                disabled={mappingType === "topology"}
              >
                {attributes.map((attribute) => (
                  <MultiSelectItem key={attribute} value={attribute}>
                    {attribute}
                  </MultiSelectItem>
                ))}
              </MultiSelect>
              {index === attributeGroups.length - 1 &&
                mappingType !== "topology" && (
                  <Button
                    onClick={addAttributeGroup}
                    color="orange"
                    size="xs"
                    variant="secondary"
                    className="flex items-center"
                    disabled={group.length === 0}
                  >
                    <PlusIcon className="w-4 h-4" />
                  </Button>
                )}
              {index > 0 && mappingType !== "topology" && (
                <Button
                  onClick={() => removeAttributeGroup(index)}
                  color="red"
                  size="xs"
                  variant="secondary"
                  className="flex items-center"
                >
                  <MinusIcon className="w-4 h-4" />
                </Button>
              )}
              {index < attributeGroups.length - 1 && (
                <Text className="mx-2">OR</Text>
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="mt-2.5">
        <Text>Enriched with</Text>
        <div className="flex flex-col gap-1 py-1">
          {attributeGroups.flat().length === 0 ? (
            <Badge color="gray">...</Badge>
          ) : (
            attributes
              .filter(
                (attribute) => !attributeGroups.flat().includes(attribute)
              )
              .map((attribute) => (
                <Badge key={attribute} color="orange">
                  {attribute}
                </Badge>
              ))
          )}
        </div>
      </div>

      <div className={"space-x-1 flex flex-row justify-end items-center"}>
        <Button
          color="orange"
          size="xs"
          variant="secondary"
          onClick={exitEditOrCreateMode}
        >
          Cancel
        </Button>

        <Button
          color="orange"
          size="xs"
          type="submit"
          disabled={!mapName || !attributeGroups.flat().length}
        >
          {editMode ? "Update" : "Create"}
        </Button>
      </div>
    </form>
  );
}
