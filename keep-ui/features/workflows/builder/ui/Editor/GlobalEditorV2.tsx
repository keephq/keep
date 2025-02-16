import React from "react";
import { EditorLayout } from "@/features/workflows/builder/ui/Editor/editors";
import { useWorkflowStore } from "@/entities/workflows";
import { Button, Divider, Icon, Subtitle, Switch, Text } from "@tremor/react";
import { WorkflowStatus } from "@/features/workflows/builder/ui/workflow-status";
import {
  BackspaceIcon,
  FunnelIcon,
  PlusIcon,
} from "@heroicons/react/24/outline";
import { TextInput } from "@/components/ui";

export function GlobalEditorV2() {
  return (
    <EditorLayout>
      <WorkflowEditorV2 />
    </EditorLayout>
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
      <Subtitle className="font-medium flex items-baseline justify-between">
        Workflow Settings{" "}
        {/* TODO: remove since user don't need to know about 'sync', it should just work */}
        <span className="text-gray-500 text-sm">
          {synced ? "Synced" : "Not Synced"}
        </span>
      </Subtitle>
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
