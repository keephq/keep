import {
  Title,
  Text,
  Select,
  SelectItem,
  Subtitle,
  Icon,
  Button,
  Switch,
  Divider,
} from "@tremor/react";
import { KeyIcon } from "@heroicons/react/20/solid";
import { Provider } from "@/app/(keep)/providers/providers";
import {
  BackspaceIcon,
  FunnelIcon,
  PlusIcon,
} from "@heroicons/react/24/outline";
import React from "react";
import useStore from "./builder-store";
import { useEffect, useRef, useState } from "react";
import { V2Properties } from "@/app/(keep)/workflows/builder/types";
import { Textarea, TextInput } from "@/components/ui";
import { DynamicIcon } from "@/components/ui";

function EditorLayout({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col m-2.5">{children}</div>;
}

export function GlobalEditorV2({
  synced,
  saveRef,
}: {
  synced: boolean;
  saveRef: React.MutableRefObject<boolean>;
}) {
  const {
    v2Properties: properties,
    updateV2Properties: setProperty,
    selectedNode,
  } = useStore();

  return (
    <EditorLayout>
      <Title>Keep Workflow Editor</Title>
      <Text>
        Use this visual workflow editor to easily create or edit existing Keep
        workflow YAML specifications.
      </Text>
      <Text className="mt-5">
        Use the edge add button or an empty step (a step with a +) to insert
        steps, conditions, and actions into your workflow. Then, click the
        Generate button to compile the workflow or the Deploy button to deploy
        it to Keep.
      </Text>
      <div className="text-right">{synced ? "Synced" : "Not Synced"}</div>
      <WorkflowEditorV2
        properties={properties}
        setProperties={setProperty}
        selectedNode={selectedNode}
        saveRef={saveRef}
      />
    </EditorLayout>
  );
}

interface keepEditorProps {
  properties: V2Properties;
  updateProperty: (key: string, value: any) => void;
  providers?: Provider[] | null | undefined;
  installedProviders?: Provider[] | null | undefined;
  providerType?: string;
  type?: string;
  isV2?: boolean;
}

function KeepStepEditor({
  properties,
  updateProperty,
  installedProviders,
  providers,
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
  const isThisProviderNeedsInstallation =
    providers?.some(
      (p) =>
        p.type === providerType && p.config && Object.keys(p.config).length > 0
    ) ?? false;

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
                icon={() => <DynamicIcon providerType={providerType!} />}
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
        value={providerConfig || ""}
        error={
          providerConfig !== "" &&
          providerConfig !== undefined &&
          isThisProviderNeedsInstallation &&
          installedProviderByType?.find(
            (p) => p.details?.name === providerConfig
          ) === undefined
        }
        errorMessage={`${
          providerConfig &&
          isThisProviderNeedsInstallation &&
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
          value={properties?.if || ("" as string)}
        />
      </div>
      <div>
        <Text>Vars</Text>
        {Object.entries(properties?.vars || {}).map(([varKey, varValue]) => (
          <div key={varKey} className="flex items-center mt-1">
            <TextInput
              placeholder={`Key ${varKey}`}
              value={varKey}
              onChange={(e) => {
                const updatedVars = {
                  ...(properties.vars as { [key: string]: string }),
                };
                delete updatedVars[varKey];
                updatedVars[e.target.value] = varValue as string;
                updateProperty("vars", updatedVars);
              }}
            />
            <TextInput
              placeholder={`Value ${varValue}`}
              value={varValue as string}
              onChange={(e) => {
                const updatedVars = {
                  ...(properties.vars as { [key: string]: string }),
                };
                updatedVars[varKey] = e.target.value;
                updateProperty("vars", updatedVars);
              }}
            />
            <Icon
              icon={BackspaceIcon}
              className="cursor-pointer"
              color="red"
              tooltip={`Remove ${varKey}`}
              onClick={() => {
                const updatedVars = {
                  ...(properties.vars as { [key: string]: string }),
                };
                delete updatedVars[varKey];
                updateProperty("vars", updatedVars);
              }}
            />
          </div>
        ))}
        <Button
          onClick={() => {
            const updatedVars = {
              ...(properties.vars as { [key: string]: string }),
              "": "",
            };
            updateProperty("vars", updatedVars);
          }}
          size="xs"
          className="ml-1 mt-1"
          variant="light"
          color="gray"
          icon={PlusIcon}
        >
          Add Var
        </Button>
      </div>
      {uniqueParams
        ?.filter((key) => key !== "kwargs")
        .map((key, index) => {
          let currentPropertyValue = ((properties.with as any) ?? {})[key];
          if (typeof currentPropertyValue === "object") {
            currentPropertyValue = JSON.stringify(currentPropertyValue);
          }
          if (key === "code") {
            return (
              <div key={index}>
                <Text>{key}</Text>
                <Textarea
                  id={`${key}`}
                  placeholder={key}
                  onChange={propertyChanged}
                  className="mb-2.5 min-h-[100px] text-xs font-mono"
                  value={currentPropertyValue || ""}
                />
              </div>
            );
          }
          return (
            <div key={index}>
              <Text>{key}</Text>
              <TextInput
                id={`${key}`}
                placeholder={key}
                onChange={propertyChanged}
                className="mb-2.5"
                value={currentPropertyValue || ""}
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
  selectedNode,
  saveRef,
}: {
  properties: V2Properties;
  setProperties: (updatedProperties: V2Properties) => void;
  selectedNode: string | null;
  saveRef: React.MutableRefObject<boolean>;
}) {
  const addNewConstant = () => {
    const updatedConsts = {
      ...(properties["consts"] as { [key: string]: string }),
      [`newKey${Object.keys(properties["consts"] || {}).length}`]: "",
    };
    handleChange("consts", updatedConsts);
  };

  const updateAlertFilter = (filter: string, value: string) => {
    const currentFilters = properties.alert || {};
    const updatedFilters = { ...currentFilters, [filter]: value };
    setProperties({ ...properties, alert: updatedFilters });
    if (saveRef.current) {
      saveRef.current = false;
    }
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
    if (saveRef.current) {
      saveRef.current = false;
    }
  };

  const handleChange = (key: string, value: string | Record<string, any>) => {
    setProperties({
      ...properties,
      [key]: value,
    });
    if (saveRef.current) {
      saveRef.current = false;
    }
  };

  const propertyKeys = Object.keys(properties).filter(
    (k) => k !== "isLocked" && k !== "id"
  );
  let renderDivider = false;
  return (
    <>
      <Title className="mt-2.5">Workflow Settings</Title>
      {propertyKeys.map((key, index) => {
        const isTrigger = ["manual", "alert", "interval", "incident"].includes(
          key
        );

        let isConst = key === "consts";
        if (isConst && !properties[key]) {
          properties[key] = {};
        }

        renderDivider =
          isTrigger && key === selectedNode ? !renderDivider : false;
        return (
          <div key={key}>
            {renderDivider && <Divider />}
            {(key === selectedNode || !isTrigger) && (
              <Text className="capitalize">{key}</Text>
            )}

            {(() => {
              switch (key) {
                case "manual":
                  return (
                    selectedNode === "manual" && (
                      <div key={key}>
                        <input
                          type="checkbox"
                          checked={true}
                          onChange={(e) =>
                            handleChange(
                              key,
                              e.target.checked ? "true" : "false"
                            )
                          }
                          disabled={true}
                        />
                      </div>
                    )
                  );

                case "alert":
                  return (
                    selectedNode === "alert" && (
                      <>
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
                                <div
                                  className="flex items-center mt-1"
                                  key={filter}
                                >
                                  <TextInput
                                    key={filter}
                                    placeholder={`Set alert ${filter}`}
                                    onChange={(e: any) =>
                                      updateAlertFilter(filter, e.target.value)
                                    }
                                    value={
                                      (properties.alert as any)[filter] ||
                                      ("" as string)
                                    }
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
                    )
                  );

                case "incident":
                  return (
                    selectedNode === "incident" && (
                      <>
                        <Subtitle className="mt-2.5">Incident events</Subtitle>
                        {Array("created", "updated", "deleted").map((event) => (
                          <div key={`incident-${event}`} className="flex">
                            <Switch
                              id={event}
                              checked={
                                properties.incident.events?.indexOf(event) > -1
                              }
                              onChange={() => {
                                let events = properties.incident.events || [];
                                if (events.indexOf(event) > -1) {
                                  events = (events as string[]).filter(
                                    (e) => e !== event
                                  );
                                  setProperties({
                                    ...properties,
                                    [key]: { events: events },
                                  });
                                } else {
                                  events.push(event);
                                  setProperties({
                                    ...properties,
                                    [key]: { events: events },
                                  });
                                }
                              }}
                              color={"orange"}
                            />
                            <label
                              htmlFor={`incident-${event}`}
                              className="text-sm text-gray-500"
                            >
                              <Text>{event}</Text>
                            </label>
                          </div>
                        ))}
                      </>
                    )
                  );
                case "interval":
                  return (
                    selectedNode === "interval" && (
                      <TextInput
                        placeholder={`Set the ${key}`}
                        onChange={(e: any) => handleChange(key, e.target.value)}
                        value={properties[key] || ("" as string)}
                      />
                    )
                  );
                case "disabled":
                  return (
                    <div key={key}>
                      <input
                        type="checkbox"
                        checked={properties[key] === "true"}
                        onChange={(e) =>
                          handleChange(key, e.target.checked ? "true" : "false")
                        }
                      />
                    </div>
                  );
                case "consts":
                  // if consts is empty, set it to an empty object
                  if (!properties[key]) {
                    return null;
                  }
                  return (
                    <div key={key}>
                      {Object.entries(
                        properties[key] as { [key: string]: string }
                      ).map(([constKey, constValue]) => (
                        <div key={constKey} className="flex items-center mt-1">
                          <TextInput
                            placeholder={`Key ${constKey}`}
                            value={constKey}
                            onChange={(e) => {
                              const updatedConsts = {
                                ...(properties[key] as {
                                  [key: string]: string;
                                }),
                              };
                              delete updatedConsts[constKey];
                              updatedConsts[e.target.value] = constValue;
                              handleChange(key, updatedConsts);
                            }}
                          />
                          <TextInput
                            placeholder={`Value ${constValue}`}
                            value={constValue}
                            onChange={(e) => {
                              const updatedConsts = {
                                ...(properties[key] as {
                                  [key: string]: string;
                                }),
                              };
                              updatedConsts[constKey] = e.target.value;
                              handleChange(key, updatedConsts);
                            }}
                          />
                          <Icon
                            icon={BackspaceIcon}
                            className="cursor-pointer"
                            color="red"
                            tooltip={`Remove ${constKey}`}
                            onClick={() => {
                              const updatedConsts = {
                                ...(properties[key] as {
                                  [key: string]: string;
                                }),
                              };
                              delete updatedConsts[constKey];
                              handleChange(key, updatedConsts);
                            }}
                          />
                        </div>
                      ))}
                      <Button
                        onClick={addNewConstant}
                        size="xs"
                        className="ml-1 mt-1"
                        variant="light"
                        color="gray"
                        icon={PlusIcon}
                      >
                        Add Constant
                      </Button>
                    </div>
                  );
                default:
                  return (
                    <TextInput
                      placeholder={`Set the ${key}`}
                      onChange={(e: any) => handleChange(key, e.target.value)}
                      value={properties[key] || ("" as string)}
                    />
                  );
              }
            })()}
          </div>
        );
      })}
    </>
  );
}

export function StepEditorV2({
  providers,
  installedProviders,
  setSynced,
  saveRef,
}: {
  providers: Provider[] | undefined | null;
  installedProviders?: Provider[] | undefined | null;
  setSynced: (sync: boolean) => void;
  saveRef: React.MutableRefObject<boolean>;
}) {
  const [formData, setFormData] = useState<{
    name?: string;
    properties?: V2Properties;
    type?: string;
  }>({});
  const { selectedNode, updateSelectedNodeData, getNodeById } = useStore();

  const deployRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (selectedNode) {
      const { data } = getNodeById(selectedNode) || {};
      const { name, type, properties } = data || {};
      setFormData({ name, type, properties });
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
    if (saveRef.current) {
      saveRef.current = false;
    }
  };

  const handleSubmit = () => {
    // Finalize the changes before saving
    updateSelectedNodeData("name", formData.name);
    updateSelectedNodeData("properties", formData.properties);
    setSynced(false);
    if (saveRef && deployRef?.current?.checked) {
      saveRef.current = true;
    }
  };

  const type = formData
    ? formData.type?.includes("step-") || formData.type?.includes("action-")
    : "";

  return (
    <EditorLayout>
      <Title className="capitalize">{providerType}1 Editor</Title>
      <Text className="mt-1">Unique Identifier</Text>
      <TextInput
        className="mb-2.5"
        icon={KeyIcon}
        name="name"
        value={formData.name || ""}
        onChange={handleInputChange}
      />
      {type && formData.properties ? (
        <KeepStepEditor
          properties={formData.properties}
          updateProperty={handlePropertyChange}
          providers={providers}
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
      <div>
        <Text className="capitalize">Deploy</Text>
        <input ref={deployRef} type="checkbox" defaultChecked />
      </div>
      <button
        className="sticky bottom-[-10px] mt-4 bg-orange-500 text-white p-2 rounded"
        onClick={handleSubmit}
      >
        Save & Deploy
      </button>
    </EditorLayout>
  );
}
