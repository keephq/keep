import {
  Title,
  Text,
  TextInput,
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
import React, { useCallback } from "react";
import { useWorkflowStore } from "@/entities/workflows";
import { useState } from "react";
import { V2Properties } from "@/entities/workflows/model/types";
import { DynamicImageProviderIcon } from "@/components/ui";
import debounce from "lodash.debounce";
import { WorkflowStatus } from "./workflow-status";

function EditorLayout({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col m-2.5">{children}</div>;
}

export function GlobalEditorV2() {
  return (
    <EditorLayout>
      <WorkflowEditorV2 />
    </EditorLayout>
  );
}

interface KeepEditorProps {
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
  providerError,
  parametersError,
}: KeepEditorProps & {
  providerError?: string | null;
  parametersError?: string | null;
}) {
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

  // TODO: move this to validateStepPure
  const providerNameError =
    providerConfig &&
    isThisProviderNeedsInstallation &&
    installedProviderByType?.find((p) => p.details?.name === providerConfig) ===
      undefined
      ? "This provider is not installed and you'll need to install it before executing this workflow."
      : "";

  return (
    <div className="flex flex-col gap-2">
      <section>
        <div className="mb-2">
          <Text className="font-bold">Provider Name</Text>
          {providerError && (
            <Text className="text-red-500">{providerError}</Text>
          )}
        </div>
        <Text className="mb-1.5">
          Select from installed {providerType} providers
        </Text>
        <Select
          className="mb-1.5"
          placeholder="Select provider"
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
                  icon={() => (
                    <DynamicImageProviderIcon
                      providerType={providerType!}
                      width="24"
                      height="24"
                      className="mr-1.5"
                    />
                  )}
                  key={providerName}
                  value={providerName}
                >
                  {providerName}
                </SelectItem>
              );
            })!
          }
        </Select>
        {/* TODO: replace with select with "create new" option */}
        <p className="text-sm text-gray-500 text-center mb-1.5">or</p>
        <Text className="mb-1.5">Enter provider name manually</Text>
        <TextInput
          placeholder="Enter provider name"
          onChange={(e: any) => updateProperty("config", e.target.value)}
          className="mb-2.5"
          value={providerConfig || ""}
          error={!!providerNameError}
          errorMessage={providerNameError ?? undefined}
        />
      </section>
      <section>
        <div className="mb-2">
          <Text className="font-bold">Provider Parameters</Text>
          {parametersError && (
            <Text className="text-red-500">{parametersError}</Text>
          )}
        </div>
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
      </section>
    </div>
  );
}

function KeepThresholdConditionEditor({
  properties,
  updateProperty,
}: KeepEditorProps) {
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
}: KeepEditorProps) {
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

function KeepForeachEditor({ properties, updateProperty }: KeepEditorProps) {
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

function WorkflowEditorV2() {
  const {
    v2Properties: properties,
    updateV2Properties,
    selectedNode,
    validationErrors,
    synced,
  } = useWorkflowStore();
  const isDeployed = useWorkflowStore((state) => state.workflowId !== null);

  const handleChange = (key: string, value: string | Record<string, any>) => {
    updateV2Properties({ [key]: value });
  };

  const addNewConstant = () => {
    const updatedConsts = {
      ...(properties["consts"] as { [key: string]: string }),
      [`newKey${Object.keys(properties["consts"] || {}).length}`]: "",
    };
    updateV2Properties({ consts: updatedConsts });
  };

  const updateAlertFilter = (filter: string, value: string) => {
    const currentFilters = properties.alert || {};
    const updatedFilters = { ...currentFilters, [filter]: value };
    updateV2Properties({ alert: updatedFilters });
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
    updateV2Properties({ alert: currentFilters });
  };

  const lockedKeys = ["isLocked", "id", "disabled"];
  const metadataKeys = ["name", "description"];
  // If workflow is not deployed, we can edit the metadata here, in side panel; otherwise we can edit via modal
  const toSkip = [...lockedKeys, ...(isDeployed ? metadataKeys : [])];

  const propertyKeys = Object.keys(properties).filter(
    (k) => !toSkip.includes(k)
  );
  let renderDivider = false;
  return (
    <>
      <Title className="flex items-baseline justify-between">
        Workflow Settings{" "}
        {/* TODO: remove since user don't need to know about 'sync', it should just work */}
        <span className="text-gray-500 text-sm">
          {synced ? "Synced" : "Not Synced"}
        </span>
      </Title>
      <WorkflowStatus className="my-2" />
      <div className="flex flex-col gap-2">
        {propertyKeys.map((key, index) => {
          const isTrigger = [
            "manual",
            "alert",
            "interval",
            "incident",
          ].includes(key);

          let isConst = key === "consts";
          if (isConst && !properties[key]) {
            properties[key] = {};
          }

          renderDivider =
            isTrigger && key === selectedNode ? !renderDivider : false;

          const errorKey = ["name", "description"].includes(key)
            ? `workflow_${key}`
            : key;
          const error = validationErrors?.[errorKey];
          return (
            <div key={key}>
              {renderDivider && <Divider />}
              {(key === selectedNode || !isTrigger) && (
                <Text className="capitalize mb-1.5">{key}</Text>
              )}

              {(() => {
                switch (key) {
                  case "manual":
                    return (
                      // TODO: explain what is manual trigger
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
                          {error && (
                            <Text className="text-red-500 mb-1.5">{error}</Text>
                          )}
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
                            Object.keys(properties.alert ?? {}).map(
                              (filter) => {
                                return (
                                  <div key={filter}>
                                    <Subtitle className="mt-2.5">
                                      {filter}
                                    </Subtitle>
                                    <div className="flex items-center mt-1">
                                      <TextInput
                                        key={filter}
                                        placeholder={`Set alert ${filter}`}
                                        onChange={(e: any) =>
                                          updateAlertFilter(
                                            filter,
                                            e.target.value
                                          )
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
                                  </div>
                                );
                              }
                            )}
                        </>
                      )
                    );

                  case "incident":
                    return (
                      selectedNode === "incident" && (
                        <>
                          <Subtitle className="mt-2.5">
                            Incident events
                          </Subtitle>
                          {Array("created", "updated", "deleted").map(
                            (event) => (
                              <div key={`incident-${event}`} className="flex">
                                <Switch
                                  id={event}
                                  checked={
                                    properties.incident.events?.indexOf(event) >
                                    -1
                                  }
                                  onChange={() => {
                                    let events =
                                      properties.incident.events || [];
                                    if (events.indexOf(event) > -1) {
                                      events = (events as string[]).filter(
                                        (e) => e !== event
                                      );
                                      updateV2Properties({
                                        [key]: { events: events },
                                      });
                                    } else {
                                      events.push(event);
                                      updateV2Properties({
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
                            )
                          )}
                        </>
                      )
                    );
                  case "interval":
                    return (
                      selectedNode === "interval" && (
                        <TextInput
                          placeholder={`Set the ${key}`}
                          onChange={(e: any) =>
                            handleChange(key, e.target.value)
                          }
                          value={properties[key] || ("" as string)}
                          error={!!error}
                          errorMessage={error}
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
                            handleChange(
                              key,
                              e.target.checked ? "true" : "false"
                            )
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
                          <div
                            key={constKey}
                            className="flex items-center mt-1"
                          >
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
                        error={!!error}
                        errorMessage={error}
                      />
                    );
                }
              })()}
            </div>
          );
        })}
      </div>
    </>
  );
}

export function StepEditorV2({
  providers,
  installedProviders,
  initialFormData,
}: {
  providers: Provider[] | undefined | null;
  installedProviders?: Provider[] | undefined | null;
  initialFormData: {
    name?: string;
    properties?: V2Properties;
    type?: string;
  };
}) {
  const [formData, setFormData] = useState<{
    name?: string;
    properties?: V2Properties;
    type?: string;
  }>(initialFormData);
  const {
    updateSelectedNodeData,
    setSynced,
    triggerSave,
    validationErrors,
    synced,
  } = useWorkflowStore();

  const saveFormDataToStoreDebounced = useCallback(
    debounce((formData: any) => {
      updateSelectedNodeData("name", formData.name);
      updateSelectedNodeData("properties", formData.properties);
    }, 300),
    [updateSelectedNodeData]
  );

  const providerType = formData?.type?.split("-")[1];

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    console.log("handleInputChange", e.target.name, e.target.value);
    const updatedFormData = { ...formData, [e.target.name]: e.target.value };
    setFormData(updatedFormData);
    setSynced(false);
    saveFormDataToStoreDebounced(updatedFormData);
  };

  const handlePropertyChange = (key: string, value: any) => {
    console.log("handlePropertyChange", key, value);
    const updatedFormData = {
      ...formData,
      properties: { ...formData.properties, [key]: value },
    };
    setFormData(updatedFormData);
    setSynced(false);
    saveFormDataToStoreDebounced(updatedFormData);
  };

  const handleSubmit = () => {
    triggerSave();
  };

  const type = formData
    ? formData.type?.includes("step-") || formData.type?.includes("action-")
    : "";

  const error = validationErrors?.[formData.name || ""];
  let parametersError = null;
  let providerError = null;
  if (error?.includes("parameters")) {
    parametersError = error;
  }

  if (error?.includes("provider")) {
    providerError = error;
  }

  return (
    <EditorLayout>
      <Title className="capitalize">{providerType} Editor</Title>
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
          providerError={providerError}
          parametersError={parametersError}
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
      <Button
        variant="primary"
        color="orange"
        className="sticky bottom-0 mt-2.5"
        onClick={handleSubmit}
        data-testid="wf-editor-save-deploy-button"
        disabled={!synced}
      >
        Save & Deploy
      </Button>
    </EditorLayout>
  );
}
