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
import React from "react";
import useStore from "./builder-store";
import { useMemo, useEffect, useRef, useState } from "react";
import { V2Properties, FlowNode } from "@/app/(keep)/workflows/builder/types";
import {
  useForm,
  Controller,
  FieldValues,
  SubmitHandler,
} from "react-hook-form";
import { toast } from "react-toastify";
import {
  methodOptions,
  requiredMap,
  getSchemaByStepType,
  FormData,
} from "./utils";
import debounce from "lodash.debounce";
import Loading from "../../loading";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

interface keepEditorProps {
  properties: V2Properties;
  updateProperty: (key: string, value: any, onlySync?: boolean) => void;
  providers?: Provider[] | null | undefined;
  installedProviders?: Provider[] | null | undefined;
  providerType?: string;
  type?: string;
  isV2?: boolean;
}
type keepEditorPropsV2 = keepEditorProps & {
  control: any;
  errors: any;
  register: any;
};

interface KeyValue {
  key: string;
  value: string;
}


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


function KeepThresholdConditionEditorV2({
  properties,
  updateProperty,
  errors,
  register,
}: keepEditorPropsV2 & {}) {
  const currentValueValue = (properties.value as string) ?? "";
  const currentCompareToValue = (properties.compare_to as string) ?? "";
  return (
    <>
      <div>
        <Text>Value</Text>
        <TextInput
          {...register("properties.value")}
          placeholder="Value"
          className="mb-2.5"
          onValueChange={(value) => {
            updateProperty("refresh", value, true);
          }}
        />
        {errors?.properties?.value && (
          <div className="text-sm text-rose-500 mt-1">
            {errors.properties.value.message?.toString()}
          </div>
        )}
      </div>
      <div>
        <Text>Compare to</Text>
        <TextInput
          {...register("properties.compare_to")}
          placeholder="Compare with"
          className="mb-2.5"
          onValueChange={(value) => {
            updateProperty("refresh", value, true);
          }}
        />
        {errors?.properties?.compare_to && (
          <div className="text-sm text-rose-500 mt-1">
            {errors.properties.compare_to.message?.toString()}
          </div>
        )}
      </div>
    </>
  );
}

function KeepAssertConditionEditorV2({
  properties,
  updateProperty,
  control,
  errors,
  register,
}: keepEditorPropsV2) {
  const currentAssertValue = (properties.assert as string) ?? "";
  return (
    <div>
      <Text>Assert</Text>
      <TextInput
        {...register("properties.assert")}
        placeholder="E.g. 200 == 200"
        className="mb-2.5"
        onValueChange={(value) => {
          updateProperty("refresh", value, true);
        }}
      />

      {errors?.properties?.assert && (
        <div className="text-sm text-rose-500 mt-1">
          {errors.properties.assert.message?.toString()}
        </div>
      )}
    </div>
  );
}

function KeepForeachEditorV2({
  properties,
  updateProperty,
  control,
  errors,
  register,
}: keepEditorPropsV2) {
  const currentValueValue = (properties.value as string) ?? "";

  return (
    <div>
      <Text>Foreach Value</Text>
      <TextInput
        {...register("properties.value")}
        placeholder="Value"
        onValueChange={(value) => {
          updateProperty("refresh", value, true);
        }}
        className="mb-2.5"
      />
      {errors?.properties?.value && (
        <div className="text-sm text-rose-500 mt-1">
          {errors.properties.value.message?.toString()}
        </div>
      )}
    </div>
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
  const { globalErrors } = useStore();
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
  const errorMap = globalErrors;
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
                        {errorMap?.manual && (
                          <div className="text-sm text-rose-500 mt-1">
                            {errorMap?.manual}
                          </div>
                        )}
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
                        {errorMap?.alert && (
                          <div className="text-sm text-rose-500 mt-1">
                            {errorMap?.alert}
                          </div>
                        )}
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
                        {errorMap?.incident && (
                          <div className="text-sm text-rose-500 mt-1">
                            {errorMap?.incident}
                          </div>
                        )}
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
                        error={!!errorMap?.interval}
                        errorMessage={errorMap?.interval}
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
                      {errorMap?.disabled && (
                        <div className="text-sm text-rose-500 mt-1">
                          {errorMap?.disabled}
                        </div>
                      )}
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
                      error={!!errorMap?.[key]}
                      errorMessage={errorMap?.[key]}
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

const useCustomForm = () => {
  const { selectedNode, updateSelectedNodeData, getNodeById } = useStore();
  const [nodeData, setNodeData] = useState<FlowNode | null>(null);

  const {
    control,
    handleSubmit,
    setValue,
    getValues,
    register,
    reset,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(getSchemaByStepType(nodeData?.data?.type)), // Default standard schema
    defaultValues: {
      name: "",
      properties: {
        with: {},
        vars: {},
        stepParams: [],
        actionParams: [],
        if: "",
      } as V2Properties,
      type: "",
    },
  });

  useEffect(() => {
    const node = getNodeById(selectedNode);

    if (node) {
      const { name, type, properties } = node?.data || {};
      setNodeData(node);

      // Get the new schema based on the node type
      const newSchema = getSchemaByStepType(type as string) || z.object({});

      // Reset the form with the new resolver and values
      reset(
        {
          name: name || "",
          type: type || "",
          properties: properties || {
            with: {},
            vars: {},
            stepParams: [],
            actionParams: [],
            if: "",
          },
        },
        { keepDefaultValues: false, keepDirty: false }
      );

      // Dynamically set the new resolver
      control._options.resolver = zodResolver(newSchema);
    }
  }, [selectedNode, getNodeById, reset, control]);

  return {
    control,
    errors,
    setValue,
    handleSubmit,
    getValues,
    nodeData,
    selectedNode,
    updateSelectedNodeData,
    register,
    loading: selectedNode !== nodeData?.id,
  };
};

export function StepEditorV3({
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
  const deployRef = useRef<HTMLInputElement>(null);
  const {
    control,
    handleSubmit,
    setValue,
    getValues,
    errors,
    selectedNode,
    updateSelectedNodeData,
    register,
    loading,
  } = useCustomForm();

  if (!selectedNode) return null;
  if (loading) {
    return <Loading />;
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValue(e.target.name, e.target.value);
    setSynced(false);
  };

  const handlePropertyChange = (
    key: string,
    value: any,
    onlySync?: boolean
  ) => {
    if (!onlySync) {
      const values = getValues();
      setValue("properties", { ...values.properties, [key]: value });
    }
    setSynced(false);
    if (saveRef.current) {
      saveRef.current = false;
    }
  };

  const values = getValues();

  const type = values.type;
  const providerType = type?.split("-")[1];
  const properties = values.properties;

  const onSubmit: SubmitHandler<FieldValues> = async (data) => {
    const { name, properties } = data || {};
    // Finalize the changes before saving
    updateSelectedNodeData("name", name || "");
    updateSelectedNodeData("properties", properties);
    setSynced(false);
    if (saveRef && deployRef?.current?.checked) {
      toast("Deploying the Changes", {
        position: "top-right",
        type: "success",
      });
      saveRef.current = true;
    } else {
      toast("Properties Successfully Saved ", {
        position: "top-right",
        type: "success",
      });
    }
  };

  const isStepOrAction =
    type?.includes("step-") || type?.includes("action-") || "";

  return (
    <EditorLayout>
      <Title className="capitalize">{providerType}1 Editor</Title>
      <form onSubmit={handleSubmit(onSubmit)}>
        <div>
          <Text className="mt-1">Unique Identifier</Text>
          <TextInput
            {...register("name")}
            className="mb-2.5"
            icon={KeyIcon}
            onValueChange={(value) => {
              handlePropertyChange("refresh", value, true);
            }}
          />
          {errors?.name && (
            <div className="text-sm text-rose-500 mt-1">
              {errors?.name.message?.toString()}
            </div>
          )}
        </div>
        {isStepOrAction ? (
          <KeepStepEditorV3
            properties={properties}
            updateProperty={handlePropertyChange}
            providers={providers}
            installedProviders={installedProviders}
            type={type}
            providerType={providerType}
            control={control}
            errors={errors}
            register={register}
          />
        ) : type === "condition-threshold" ? (
          <KeepThresholdConditionEditorV2
            properties={properties!}
            updateProperty={handlePropertyChange}
            control={control}
            errors={errors}
            register={register}
          />
        ) : type?.includes("foreach") ? (
          <KeepForeachEditorV2
            properties={properties!}
            updateProperty={handlePropertyChange}
            control={control}
            errors={errors}
            register={register}
          />
        ) : type === "condition-assert" ? (
          <KeepAssertConditionEditorV2
            properties={properties!}
            updateProperty={handlePropertyChange}
            control={control}
            errors={errors}
            register={register}
          />
        ) : null}
        <div>
          <Text className="capitalize">Deploy</Text>
          <input ref={deployRef} type="checkbox" defaultChecked />
        </div>
        <Button
          className={`w-full sticky bottom-[-10px] mt-4  text-white p-2 rounded ${!errors ? "bg-orange-200 cursor-not-allowed" : "bg-orange-500"}`}
          disabled={!errors}
          type="submit"
        >
          Save & Deploy
        </Button>
      </form>
    </EditorLayout>
  );
}

export function KeyValueForm({
  properties,
  initialPairs,
  updateProperty,
}: {
  properties: any;
  initialPairs?: KeyValue[];
  updateProperty: (value: any) => void;
}) {
  const [pairs, setPairs] = useState<KeyValue[]>(
    initialPairs || ([] as KeyValue[])
  );
  const [error, setError] = useState<string>("");

  const handleKeyChange = (index: number, newKey: string) => {
    const updatedPairs = [...pairs];
    setError("");
    updatedPairs[index].key = newKey;
    setPairs(updatedPairs);
  };

  const handleValueChange = (index: number, newValue: string) => {
    const updatedPairs = [...pairs];
    updatedPairs[index].value = newValue;
    setPairs(updatedPairs);
  };

  const handleAddField = () => {
    const lastPair = pairs[pairs.length - 1];

    // Ensure the last key is filled before adding a new field
    if (pairs.length && lastPair?.key?.trim() === "") {
      setError("Key cannot be empty.");
      return;
    }

    setError("");
    setPairs([...pairs, { key: "", value: "" }]);
  };

  useEffect(() => {
    const vars =
      pairs?.reduce<Record<string, string>>((obj, pair) => {
        if (pair.key) {
          obj[pair.key] = pair.value;
        }
        return obj;
      }, {}) || {};

    const debouncedUpdate = debounce(() => {
      updateProperty(vars);
    }, 300);

    if (
      properties &&
      JSON.stringify(properties.vars) !== JSON.stringify(vars)
    ) {
      debouncedUpdate();
    }
    // Cleanup the debounce on unmount or if dependencies change
    return () => {
      debouncedUpdate.cancel();
    };
  }, [pairs, properties, updateProperty]);

  return pairs ? (
    <div>
      <Text>Vars</Text>
      {pairs?.map((pair, index) => (
        <div key={index} className="flex items-center mb-3">
          <TextInput
            placeholder="Key"
            value={pair.key}
            onValueChange={(value) => handleKeyChange(index, value)}
          />
          <TextInput
            placeholder="Value"
            value={pair.value}
            onValueChange={(value) => handleValueChange(index, value)}
          />
          <Icon
            icon={BackspaceIcon}
            className="cursor-pointer"
            color="red"
            tooltip={`Remove ${pair.key}`}
            onClick={(e) => {
              e.preventDefault();
              setPairs([...pairs.slice(0, index), ...pairs.slice(index + 1)]);
            }}
          />
        </div>
      ))}
      {error && <div className="text-red-500 text-sm mb-2">{error}</div>}
      <Button
        onClick={(e) => {
          e.preventDefault();
          handleAddField();
        }}
        size="xs"
        className="ml-1 mt-1"
        variant="light"
        color="gray"
        type="button"
        icon={PlusIcon}
      >
        Add Var
      </Button>
    </div>
  ) : null;
}

function KeepStepEditorV3({
  properties,
  updateProperty,
  installedProviders,
  providers,
  type,
  control,
  errors,
  providerType,
  register,
}: keepEditorPropsV2 & { register: any }) {
  const { stepErrors, selectedNode, errorNode } = useStore();
  const errorKeys = Object.keys(errors || {})?.toString();
  const pickInitialErros = useMemo(()=>{
      if(errorKeys) {
        return false;
      }
      return errorNode === selectedNode;
  }, [errorKeys, selectedNode, errorNode]);

  function propertyChanged(key: string, value: any) {
    const currentWith = (properties.with as object) ?? {};
    updateProperty("with", { ...currentWith, [key]: value });
  }
  const stepParams =
    ((type?.includes("step-")
      ? properties.stepParams
      : properties.actionParams) as string[]) ?? [];
  const existingParams = Object.keys((properties.with as object) ?? {});
  const uniqueParams = [...new Set([...stepParams, ...existingParams])];

  const providerConfig = properties?.config?.trim();
  const installedProviderByType = installedProviders?.filter(
    (p) => p.type === providerType
  );

  const isHttpAction = type === "action-http";
  const isThisProviderNeedsInstallation =
    (!isHttpAction &&
      providers?.some(
        (p) =>
          p.type === providerType &&
          p.config &&
          Object.keys(p.config).length > 0
      )) ??
    false;

  const tempRequiredKeys = type ? [...(requiredMap[type] || [])] : [];

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

  const varPairs = Object.entries(properties?.vars || {}).map(
    ([key, value]) => ({ key, value })
  ) as KeyValue[];
  return (
    <>
      {!isHttpAction && (
        <>
          <div>
            <Text>Provider Name</Text>
            <Controller
              name="properties.config"
              control={control}
              render={({ field: { value, onChange, ...field } }) => {
                const providerConfig = value?.trim() || "";
                return (
                  <div>
                    <Select
                      {...field}
                      className="my-2.5"
                      placeholder={`Select from installed ${providerType} providers`}
                      disabled={
                        installedProviderByType?.length === 0 ||
                        !installedProviderByType
                      }
                      error={!!(pickInitialErros&& stepErrors?.["properties.config"])}
                      errorMessage={pickInitialErros ? stepErrors?.["properties.config"] : ""}
                      value={providerConfig}
                      onValueChange={(value) => {
                        updateProperty("refresh", value, true);
                        onChange(value);
                      }}                    >
                      {
                        installedProviderByType?.map((provider) => {
                          const providerName =
                            provider.details?.name ?? provider.id;
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
                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        Provider Name
                      </label>
                      <TextInput
                        {...field}
                        className="mb-2.5"
                        placeholder="Enter provider name manually"
                        value={providerConfig}
                        onValueChange={(value) => {
                          updateProperty("refresh", value, true);
                          onChange(value);
                        }}                        
                        //TODO: move it to zod validations.
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
                    </div>
                  </div>
                );
              }}
            />
            {errors?.properties?.config && (
              <div className="text-sm text-rose-500 mt-1">
                {errors.properties.config.message?.toString()}
              </div>
            )}
          </div>
          <Text className="my-2.5">Provider Parameters</Text>
        </>
      )}
      <div>
        <label className="block text-sm font-medium text-gray-700">If</label>
        <TextInput
          {...register("properties.if")}
          placeholder="if"
          error={
            !!errors?.properties?.if || (pickInitialErros && !!stepErrors?.[`properties.with.if`])
          }
          errorMessage={
            errors?.properties?.if?.message?.toString() ||
            (pickInitialErros ? stepErrors?.[`properties.with.if`] : "")
          }
          onValueChange={(value) => {
            updateProperty("refresh", value, true);
          }}
        />
      </div>
      <div>
        {/* fixed the vars key value issue.(key is not getting updated properly)*/}
        <Controller
          name={`properties.vars`}
          control={control}
          render={({ field }) => (
            <KeyValueForm
              properties={properties}
              initialPairs={varPairs}
              updateProperty={(value: any) => field.onChange(value)}
            />
          )}
        />
      </div>
      {uniqueParams
        ?.filter((key) => key !== "kwargs")
        .map((key, index) => {
          let currentPropertyValue = ((properties.with as any) ?? {})[key];
          if (typeof currentPropertyValue === "object") {
            currentPropertyValue = JSON.stringify(currentPropertyValue);
          }
          let requiredKeys = tempRequiredKeys || [];
          if (key === "method" && isHttpAction) {
            return (
              <div key={key}>
                <Text>
                  {key}{" "}
                  {requiredKeys?.includes(key) ? (
                    <span className="text-red-500">*</span>
                  ) : (
                    ""
                  )}
                </Text>
                <Controller
                  name="properties.with.method"
                  control={control}
                  render={({ field:{onChange, ...field} }) => (
                    <Select
                      {...field}
                      onValueChange={(value) => {
                        updateProperty("refresh", value, true);
                        onChange(value);
                      }}
                      placeholder="Select Method"
                      error={
                        !!errors?.properties?.with?.[key] ||
                        (pickInitialErros&& !!stepErrors?.[`properties.with.${key}`])
                      }
                      errorMessage={
                        errors?.properties?.with?.[key]?.message?.toString() ||
                        (pickInitialErros ? stepErrors?.[`properties.with.${key}`] : "")
                      }
                    >
                      {methodOptions?.map(({ key, value }) => (
                        <SelectItem key={key} value={value}>
                          {key?.toUpperCase()}
                        </SelectItem>
                      ))}
                    </Select>
                  )}
                />
              </div>
            );
          }
          if (key === "body" && isHttpAction) {
            if (["POST", "PUT", "PATCH"].includes(properties?.with?.method)) {
              requiredKeys = [...tempRequiredKeys, "body"];
            }
          }
          return (
            <div key={key}>
              <label className="block text-sm font-medium text-gray-700">
                {key}{" "}
                {requiredKeys?.includes(key) ? (
                  <span className="text-red-500">*</span>
                ) : (
                  ""
                )}
              </label>
              <Controller
                name={`properties.with.${key}`}
                control={control}
                defaultValue=""
                render={({ field: { value, ...field } }) => {
                  let currentPropertyValue = ((properties.with as any) ?? {})[
                    key
                  ];
                  if (typeof currentPropertyValue === "object") {
                    currentPropertyValue = JSON.stringify(currentPropertyValue);
                  }
                  return (
                    <TextInput
                      {...field}
                      placeholder={`Enter ${key}`}
                      defaultValue={currentPropertyValue}
                      onValueChange={(value) =>
                        updateProperty("refresh", value, true)
                      }
                      error={
                        !!errors?.properties?.with?.[key] ||
                        (pickInitialErros && !!stepErrors?.[`properties.with.${key}`])
                      }
                      errorMessage={
                        errors?.properties?.with?.[key]?.message?.toString() ||
                        (pickInitialErros ? stepErrors?.[`properties.with.${key}`] : "")
                      }
                    />
                  );
                }}
              />
            </div>
          );
        })}
    </>
  );
}
