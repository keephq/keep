import {
  Title,
  Text,
  TextInput,
  Select,
  SelectItem,
  Subtitle,
  Icon,
  Button,
} from "@tremor/react";
import { KeyIcon } from "@heroicons/react/20/solid";
import { Provider } from "app/providers/providers";
import {
  BackspaceIcon,
  BellSnoozeIcon,
  ClockIcon,
  FunnelIcon,
  HandRaisedIcon,
} from "@heroicons/react/24/outline";
import useStore, { V2Properties } from "./builder-store";
import { useEffect, useState } from "react";

function EditorLayout({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col m-2.5">{children}</div>;
}


export function GlobalEditorV2({synced}: {synced: boolean}) {
  const { v2Properties: properties, updateV2Properties: setProperty, selectedNode } = useStore();

  return (
    <EditorLayout>
      <Title>Keep Workflow Editor</Title>
      <Text>
        Use this visual workflow editor to easily create or edit existing Keep
        workflow YAML specifications.
      </Text>
      <Text className="mt-5">
        Use the edge add button or an empty step (a step with a +) to insert steps, conditions, and actions into your workflow.
        Then, click the Generate button to compile the workflow or the Deploy button to deploy it to Keep.
      </Text>
      <div className="text-right">{synced ? "Synced" : "Not Synced"}</div>
      <WorkflowEditorV2
        properties={properties}
        setProperties={setProperty}
        selectedNode={selectedNode}
      />
    </EditorLayout>
  );
}


interface keepEditorProps {
  properties: V2Properties;
  updateProperty: ((key: string, value: any) => void);
  installedProviders?: Provider[] | null | undefined;
  providerType?: string;
  type?: string;
  isV2?:boolean
}

function KeepStepEditor({
  properties,
  updateProperty,
  installedProviders,
  providerType,
  type,
}: keepEditorProps) {
  const stepParams =
    ((type?.includes("step-")
      ? properties.stepParams
      : properties.actionParams) as string[]) ?? [];
  const existingParams = Object.keys((properties.with as object) ?? {});
  const params = [...stepParams, ...existingParams];
  const uniqueParams = params.filter(
    (item, pos) => params.indexOf(item) === pos
  );

  function propertyChanged(e: any) {
    const currentWith = (properties.with as object) ?? {};
    updateProperty("with", { ...currentWith, [e.target.id]: e.target.value });
  }

  const providerConfig = (properties.config as string)?.trim();
  const installedProviderByType = installedProviders?.filter(
    (p) => p.type === providerType
  );

  const DynamicIcon = (props: any) => (
    <svg
      width="24px"
      height="24px"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      {...props}
    >
      {" "}
      <image
        id="image0"
        width={"24"}
        height={"24"}
        href={`/icons/${providerType}-icon.png`}
      />
    </svg>
  );

  return (
    <>
      <Text>Provider Name</Text>
      <Select
        className="my-2.5"
        placeholder={`Select from installed ${providerType} providers`}
        disabled={
          installedProviderByType?.length === 0 || !installedProviderByType
        }
        onValueChange={(value) => updateProperty("config", value)}
      >
        {
          installedProviderByType?.map((provider) => {
            const providerName = provider.details?.name ?? provider.id;
            return (
              <SelectItem
                icon={DynamicIcon}
                key={providerName}
                value={providerName}
              >
                {providerName}
              </SelectItem>
            );
          })!
        }
      </Select>
      <Subtitle>Or</Subtitle>
      <TextInput
        placeholder="Enter provider name manually"
        onChange={(e: any) => updateProperty("config", e.target.value)}
        className="my-2.5"
        value={providerConfig}
        error={
          providerConfig !== "" &&
          providerConfig !== undefined &&
          installedProviderByType?.find(
            (p) => p.details?.name === providerConfig
          ) === undefined
        }
        errorMessage={`${
          providerConfig &&
          installedProviderByType?.find(
            (p) => p.details?.name === providerConfig
          ) === undefined
            ? "Please note this provider is not installed and you'll need to install it before executing this workflow."
            : ""
        }`}
      />
      <Text className="my-2.5">Provider Parameters</Text>
      <div>
        <Text>If</Text>
        <TextInput
          id="if"
          placeholder="If Condition"
          onValueChange={(value) => updateProperty("if", value)}
          className="mb-2.5"
          value={properties?.if as string}
        />
      </div>
      {uniqueParams
        ?.filter((key) => key !== "kwargs")
        .map((key, index) => {
          let currentPropertyValue = ((properties.with as any) ?? {})[key];
          if (typeof currentPropertyValue === "object") {
            currentPropertyValue = JSON.stringify(currentPropertyValue);
          }
          return (
            <div key={index}>
              <Text>{key}</Text>
              <TextInput
                id={`${key}`}
                placeholder={key}
                onChange={propertyChanged}
                className="mb-2.5"
                value={currentPropertyValue}
              />
            </div>
          );
        })}
    </>
  );
}

function KeepThresholdConditionEditor({
  properties,
  updateProperty,
}: keepEditorProps) {
  const currentValueValue = (properties.value as string) ?? "";
  const currentCompareToValue = (properties.compare_to as string) ?? "";
  return (
    <>
      <Text>Value</Text>
      <TextInput
        placeholder="Value"
        onChange={(e: any) => updateProperty("value", e.target.value)}
        className="mb-2.5"
        value={currentValueValue}
      />
      <Text>Compare to</Text>
      <TextInput
        placeholder="Compare with"
        onChange={(e: any) => updateProperty("compare_to", e.target.value)}
        className="mb-2.5"
        value={currentCompareToValue}
      />
    </>
  );
}

function KeepAssertConditionEditor({
  properties,
  updateProperty,
}: keepEditorProps) {
  const currentAssertValue = (properties.assert as string) ?? "";
  return (
    <>
      <Text>Assert</Text>
      <TextInput
        placeholder="E.g. 200 == 200"
        onChange={(e: any) => updateProperty("assert", e.target.value)}
        className="mb-2.5"
        value={currentAssertValue}
      />
    </>
  );
}

function KeepForeachEditor({ properties, updateProperty }: keepEditorProps) {
  const currentValueValue = (properties.value as string) ?? "";

  return (
    <>
      <Text>Foreach Value</Text>
      <TextInput
        placeholder="Value"
        onChange={(e: any) => updateProperty("value", e.target.value)}
        className="mb-2.5"
        value={currentValueValue}
      />
    </>
  );
}

function WorkflowEditorV2({
  properties,
  setProperties,
  selectedNode
}: {
  properties: V2Properties;
  setProperties: (updatedProperties: V2Properties) => void;
  selectedNode: string | null;
}) {
  const isTrigger = ['interval', 'manual', 'alert'].includes(selectedNode || '')


  const updateAlertFilter = (filter: string, value: string) => {
    const currentFilters = properties.alert || {};
    const updatedFilters = { ...currentFilters, [filter]: value };
    setProperties({ ...properties, alert: updatedFilters });
  };

  const addFilter = () => {
    const filterName = prompt("Enter filter name");
    if (filterName) {
      updateAlertFilter(filterName, "");
    }
  };


  const deleteFilter = (filter: string) => {
    const currentFilters = { ...properties.alert };
    delete currentFilters[filter];
    setProperties({ ...properties, alert: currentFilters });
  };

  const propertyKeys = Object.keys(properties).filter(
    (k) => k !== "isLocked" && k !== "id"
  );

  return (
    <>
      <Title className="mt-2.5">Workflow Settings</Title>
      {propertyKeys.map((key, index) => {
        return (
           <div key={index}>
            {((key ===  selectedNode)||(!["manual", "alert", 'interval'].includes(key))) && <Text className="capitalize mt-2.5">{key}</Text>}
            {key === "manual" ? (
              selectedNode === 'manual' && <div key={key}>
                <input
                  type="checkbox"
                  checked={properties[key] === "true"}
                  onChange={(e) =>
                    setProperties({
                      ...properties,
                      [key]: e.target.checked ? "true" : "false",
                    })
                  }
                />
              </div>
            ) : key === "alert" ? (
              selectedNode === 'alert' && <>
                 <div className="w-1/2">
                  <Button
                    onClick={addFilter}
                    size="xs"
                    className="ml-1 mt-1"
                    variant="light"
                    color="gray"
                    icon={FunnelIcon}
                  >
                    Add Filter
                  </Button>
                </div>
                {properties.alert &&
                  Object.keys(properties.alert as {}).map((filter) => {
                    return (
                      <>
                        <Subtitle className="mt-2.5">{filter}</Subtitle>
                        <div className="flex items-center mt-1" key={filter}>
                          <TextInput
                            key={filter}
                            placeholder={`Set alert ${filter}`}
                            onChange={(e: any) =>
                              updateAlertFilter(filter, e.target.value)
                            }
                            value={(properties.alert as any)[filter] as string}
                          />
                          <Icon
                            icon={BackspaceIcon}
                            className="cursor-pointer"
                            color="red"
                            tooltip={`Remove ${filter} filter`}
                            onClick={() => deleteFilter(filter)}
                          />
                        </div>
                      </>
                    );
                  })}
              </>
            ) : key === "interval" ? (
               selectedNode === 'interval' && <TextInput
                placeholder={`Set the ${key}`}
                onChange={(e: any) =>
                  setProperties({ ...properties, [key]: e.target.value })
                }
                value={properties[key] as string}
              />
            ): <TextInput
            placeholder={`Set the ${key}`}
            onChange={(e: any) =>
              setProperties({ ...properties, [key]: e.target.value })
            }
            value={properties[key] as string}
          />}
            
          </div>
        );
      })}
    </>
  );
}



export function StepEditorV2({
  installedProviders,
  setSynced
}: {
  installedProviders?: Provider[] | undefined | null;
  setSynced: (sync:boolean) => void;
}) {
  const [formData, setFormData] = useState<{ name?: string; properties?: V2Properties, type?:string }>({});
  const { 
    selectedNode,
    updateSelectedNodeData,
    setOpneGlobalEditor,
    getNodeById
  } = useStore();

  useEffect(() => {
    if (selectedNode) {
      const { data } = getNodeById(selectedNode) || {};
      const { name, type, properties } = data || {};
      setFormData({ name, type , properties });
    }
  }, [selectedNode, getNodeById]);

  if (!selectedNode) return null;

  const providerType = formData?.type?.split("-")[1];

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setSynced(false);
  };

  const handlePropertyChange = (key: string, value: any) => {
    setFormData({
      ...formData,
      properties: { ...formData.properties, [key]: value },
    });
    setSynced(false);
  };


  const handleSubmit = () => {
    // Finalize the changes before saving
    updateSelectedNodeData('name', formData.name);
    updateSelectedNodeData('properties', formData.properties);
  };

  const type = formData ? formData.type?.includes("step-") || formData.type?.includes("action-") : "";

  return (
    <EditorLayout>
      <Title className="capitalize">{providerType} Editor</Title>
      <Text className="mt-1">Unique Identifier</Text>
      <TextInput
        className="mb-2.5"
        icon={KeyIcon}
        name="name"
        value={formData.name || ''}
        onChange={handleInputChange}
      />
      {type  && formData.properties ? (
        <KeepStepEditor
          properties={formData.properties}
          updateProperty={handlePropertyChange}
          installedProviders={installedProviders}
          providerType={providerType}
          type={formData.type}
        />
      ) : formData.type === "condition-threshold" ? (
        <KeepThresholdConditionEditor
          properties={formData.properties!}
          updateProperty={handlePropertyChange}
        />
      ) : formData.type?.includes("foreach") ? (
        <KeepForeachEditor
          properties={formData.properties!}
          updateProperty={handlePropertyChange}
        />
      ) : formData.type === "condition-assert" ? (
        <KeepAssertConditionEditor
          properties={formData.properties!}
          updateProperty={handlePropertyChange}
        />
      ) : null}
      <button
        className="mt-4 bg-orange-500 text-white p-2 rounded"
        onClick={handleSubmit}
      >
        Save
      </button>
    </EditorLayout>
  );
}