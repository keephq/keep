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
} from "@tremor/react";
import { useSession } from "next-auth/react";
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
import { useApiUrl } from "utils/hooks/useConfig";
import { useMappings } from "utils/hooks/useMappingRules";
import { MappingRule } from "./models";
import { CreateableSearchSelect } from "@/components/ui/CreateableSearchSelect";
import { useTopology } from "@/app/topology/model";

interface Props {
  editRule: MappingRule | null;
  editCallback: (rule: MappingRule | null) => void;
}

export default function CreateOrEditMapping({ editRule, editCallback }: Props) {
  const { data: session } = useSession();
  const { mutate } = useMappings();
  const [tabIndex, setTabIndex] = useState<number>(0);
  const [mapName, setMapName] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");
  const [mappingType, setMappingType] = useState<"csv" | "topology">("csv");
  const [mapDescription, setMapDescription] = useState<string>("");
  const [selectedLookupAttributes, setSelectedLookupAttributes] = useState<
    string[]
  >([]);
  const { topologyData } = useTopology();
  const [priority, setPriority] = useState<number>(0);
  const editMode = editRule !== null;
  const inputFile = useRef<HTMLInputElement>(null);
  const apiUrl = useApiUrl();

  // This useEffect runs whenever an `Edit` button is pressed in the table, and populates the form with the mapping data that needs to be edited.
  useEffect(() => {
    if (editRule !== null) {
      handleFileReset();
      setMapName(editRule.name);
      setFileName(editRule.file_name ? editRule.file_name : "");
      setMapDescription(editRule.description ? editRule.description : "");
      setMappingType(editRule.type ? editRule.type : "csv");
      setTabIndex(editRule.type === "csv" ? 0 : 1);
      setSelectedLookupAttributes(editRule.matchers ? editRule.matchers : []);
      setPriority(editRule.priority);
    }
  }, [editRule]);

  /** This is everything related with the uploaded CSV file */
  const [parsedData, setParsedData] = useState<any[] | null>(null);
  const attributes = useMemo(() => {
    if (parsedData) {
      setSelectedLookupAttributes([]);
      return Object.keys(parsedData[0]);
    }

    // If we are in the editMode then we need to generate attributes i.e. [selectedAttributes + matchers]
    if (editRule) {
      return [
        ...(editRule.attributes ? editRule.attributes : []),
        ...editRule.matchers,
      ];
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
    } else {
      setParsedData(topologyData!);
      setMappingType("topology");
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
    setSelectedLookupAttributes([]);
    handleFileReset();
  };

  const addRule = async (e: FormEvent) => {
    e.preventDefault();
    const response = await fetch(`${apiUrl}/mapping`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        priority: priority,
        name: mapName,
        description: mapDescription,
        file_name: fileName,
        type: mappingType,
        matchers: selectedLookupAttributes.map((attr) => attr.trim()),
        rows: mappingType === "csv" ? parsedData : null,
      }),
    });
    if (response.ok) {
      clearForm();
      mutate();
      toast.success("Mapping created successfully");
    } else {
      toast.error(
        "Failed to create mapping, please contact us if this issue persists."
      );
    }
  };

  // This is the function that will be called on submitting the form in the editMode, it sends a PUT request to the backennd.
  const updateRule = async (e: FormEvent) => {
    e.preventDefault();
    const response = await fetch(`${apiUrl}/mapping/${editRule?.id}`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        id: editRule?.id,
        priority: priority,
        name: mapName,
        description: mapDescription,
        file_name: fileName,
        type: mappingType,
        matchers: selectedLookupAttributes.map((attr) => attr.trim()),
        rows: mappingType === "csv" ? parsedData : null,
      }),
    });
    if (response.ok) {
      exitEditMode();
      mutate();
      toast.success("Mapping updated successfully");
    } else {
      toast.error(
        "Failed to update mapping, please contact us if this issue persists."
      );
    }
  };

  // If the mapping is successfully updated or the user cancels the update we exit the editMode and set the editRule in the mapping.tsx to null.
  const exitEditMode = async () => {
    editCallback(null);
    clearForm();
  };

  const submitEnabled = (): boolean => {
    return (
      !!mapName &&
      selectedLookupAttributes.length > 0 &&
      (editMode || !!parsedData) &&
      attributes.filter(
        (attribute) => !selectedLookupAttributes.includes(attribute)
      ).length > 0
    );
  };

  return (
    <form className="max-w-lg py-2" onSubmit={editMode ? updateRule : addRule}>
      <Subtitle>Mapping Metadata</Subtitle>
      <div className="mt-2.5">
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
      <div className="mt-2.5">
        <Text>Description</Text>
        <Textarea
          placeholder="Map Description"
          value={mapDescription}
          onValueChange={setMapDescription}
        />
      </div>
      <div className="mt-2.5">
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
                <input
                  type="file"
                  accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
                  onChange={readFile}
                  required={!editMode}
                  ref={inputFile}
                />
              )}
              {!parsedData && (
                <Text className="text-xs text-red-500">
                  {!editMode
                    ? "* Upload a CSV file to begin with creating a new mapping"
                    : ""}
                </Text>
              )}
            </TabPanel>
            <TabPanel></TabPanel>
          </TabPanels>
        </TabGroup>
      </div>
      <Subtitle className="mt-2.5">Mapping Schema</Subtitle>
      <div className="mt-2.5">
        <Text>Alert lookup attributes to match against the uploaded CSV</Text>
        <Text className="text-xs">
          (E.g. the attributes that we will try to match before enriching)
        </Text>
        <CreateableSearchSelect
          onFieldChange={(key, val) => {
            setSelectedLookupAttributes(val.split("||"));
          }}
          selectId="0"
          options={attributes}
          disabled={!editMode && !parsedData}
          defaultValue={selectedLookupAttributes.join("||")}
          className="mt-1"
        />
        <Text className="text-xs mt-1">
          (Use `&&` to match multiple attributes at once and `||` to
          condtionally match others)
        </Text>
        <Text className="text-xs mt-2">
          For example: `tags.service_name || labels.service_name` will match if
          either `tags.service_name` or `labels.service_name` is present in the
          alert and matches the CSV.
        </Text>
      </div>
      <div className="mt-2.5">
        <Text>Result attributes</Text>
        <Text className="text-xs">
          (E.g. attributes that will be added to matching incoming alerts)
        </Text>
        <div className="flex flex-col gap-1 py-1">
          {selectedLookupAttributes.length === 0 ? (
            <Badge color="gray">...</Badge>
          ) : (
            attributes
              .filter((attribute) => {
                return !selectedLookupAttributes.some((lookupAttr) => {
                  const parts = lookupAttr
                    .split("&&")
                    .map((part) => part.trim());
                  return parts.includes(attribute);
                });
              })
              .map((attribute) => (
                <Badge key={attribute} color="orange">
                  {attribute}
                </Badge>
              ))
          )}
        </div>
      </div>
      <div className={"space-x-1 flex flex-row justify-end items-center"}>
        {/*If we are in the editMode we need an extra cancel button option for the user*/}
        {editMode ? (
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            onClick={exitEditMode}
          >
            Cancel
          </Button>
        ) : (
          <></>
        )}
        <Button
          disabled={!submitEnabled()}
          color="orange"
          size="xs"
          type="submit"
        >
          {editMode ? "Update" : "Create"}
        </Button>
      </div>
    </form>
  );
}
