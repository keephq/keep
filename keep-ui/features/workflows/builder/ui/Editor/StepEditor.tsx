import {
  Button,
  Callout,
  Icon,
  Select,
  SelectItem,
  Subtitle,
  Tab,
  TabGroup,
  TabList,
  TabPanel,
  TabPanels,
  Text,
} from "@tremor/react";
import { KeyIcon } from "@heroicons/react/20/solid";
import { Provider } from "@/shared/api/providers";
import {
  BackspaceIcon,
  PencilIcon,
  PlusIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import {
  ExclamationCircleIcon,
  CheckCircleIcon,
} from "@heroicons/react/20/solid";
import React, { useCallback, useMemo, useState } from "react";
import { useWorkflowStore } from "@/entities/workflows";
import {
  NodeDataStepSchema,
  V2ActionStep,
  V2Properties,
  V2StepConditionAssert,
  V2StepConditionThreshold,
  V2StepForeach,
  V2StepStep,
} from "@/entities/workflows/model/types";
import { DynamicImageProviderIcon, TextInput } from "@/components/ui";
import debounce from "lodash.debounce";
import { TestRunStepForm } from "./StepTest";
import { checkProviderNeedsInstallation } from "@/entities/workflows/model/validation";
import { EditorField } from "@/features/workflows/builder/ui/Editor/EditorField";
import { useProviders } from "@/utils/hooks/useProviders";
import ProviderForm from "@/app/(keep)/providers/provider-form";
import { Drawer } from "@/shared/ui/Drawer";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";

export function EditorLayout({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex flex-col mx-4 my-2.5 ${className}`}>{children}</div>
  );
}

function KeyValueListField({
  keyValueList,
  onChange,
}: {
  keyValueList: { key: string; value: string }[];
  onChange: (value: any) => void;
}) {
  if (!keyValueList || !Array.isArray(keyValueList)) {
    return null;
  }
  return (
    <div className="flex flex-col gap-2 items-start">
      {keyValueList.map((item, index) => (
        <div key={index} className="flex items-center gap-1">
          <TextInput
            placeholder={`Key ${item.key}`}
            value={item.key}
            className="min-w-0"
            onChange={(e) => {
              const updatedKeyValueList = [...keyValueList];
              updatedKeyValueList[index].key = e.target.value;
              onChange(updatedKeyValueList);
            }}
          />
          <TextInput
            placeholder={`Value ${item.value}`}
            value={item.value as string}
            className="min-w-0"
            onChange={(e) => {
              const updatedKeyValueList = [...keyValueList];
              updatedKeyValueList[index].value = e.target.value;
              onChange(updatedKeyValueList);
            }}
          />
          <Button
            variant="light"
            color="gray"
            icon={TrashIcon}
            className="cursor-pointer hover:text-red-500"
            tooltip={`Remove ${item.key}`}
            onClick={() => {
              const updatedKeyValueList = [...keyValueList];
              updatedKeyValueList.splice(index, 1);
              onChange(updatedKeyValueList);
            }}
          />
        </div>
      ))}
      <Button
        onClick={() => {
          const updatedKeyValueList = [...keyValueList];
          updatedKeyValueList.push({ key: "", value: "" });
          onChange(updatedKeyValueList);
        }}
        size="xs"
        className="ml-1 mt-1"
        variant="light"
        color="gray"
        icon={PlusIcon}
      >
        Add key-value pair
      </Button>
    </div>
  );
}

export interface KeepEditorProps {
  properties: V2Properties;
  updateProperty: (key: string, value: any) => void;
  providers?: Provider[] | null | undefined;
  installedProviders?: Provider[] | null | undefined;
  providerType?: string;
  type?: string;
  isV2?: boolean;
}

function InstallProviderButton({ providerType }: { providerType: string }) {
  const { data: { providers } = {} } = useProviders();
  const revalidateMultiple = useRevalidateMultiple();
  const providerObject = providers?.find((p) => p.type === providerType);
  const [isFormOpen, setIsFormOpen] = useState(false);

  if (!providerObject) {
    return null;
  }

  const onConnectClick = () => {
    setIsFormOpen(true);
  };

  return (
    <>
      <Button
        onClick={onConnectClick}
        disabled={providerObject.installed}
        className="w-full text-black"
        variant="secondary"
        color="neutral"
        size="sm"
        icon={() => (
          <DynamicImageProviderIcon
            className="mr-1"
            src={`/icons/${providerObject.type}-icon.png`}
            width={24}
            height={24}
            alt={providerObject.type}
          />
        )}
      >
        Install {""}
        <span className="text-sm capitalize">
          {providerObject.display_name}
        </span>
      </Button>
      <Drawer
        title={`Connect to ${providerObject.display_name}`}
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
      >
        <ProviderForm
          provider={{ ...providerObject, id: providerObject.type }}
          installedProvidersMode={false}
          mutate={() => {
            revalidateMultiple(["providers"], { isExact: true });
          }}
          closeModal={() => setIsFormOpen(false)}
          isProviderNameDisabled={false}
          isLocalhost={false}
          isHealthCheck={false}
        />
      </Drawer>
    </>
  );
}

function KeepSetupProviderEditor({
  properties,
  updateProperty,
  providerType,
  providerError,
}: KeepEditorProps & {
  providerError?: string | null;
  providerNameError?: string | null;
}) {
  const { data: { providers, installed_providers: installedProviders } = {} } =
    useProviders();
  const providerObject =
    providers?.find((p) => p.type === providerType) ?? null;

  const installedProviderByType = installedProviders?.filter(
    (p) => p.type === providerType
  );
  const doesProviderNeedInstallation = providerObject
    ? checkProviderNeedsInstallation(providerObject)
    : false;
  const providerConfig = !doesProviderNeedInstallation
    ? "default-" + providerType
    : (properties.config ?? "")?.trim();

  const isCustomConfig =
    installedProviderByType?.find((p) => p.details?.name === providerConfig) ===
      undefined && providerConfig;

  const [selectValue, setSelectValue] = useState(
    isCustomConfig ? "enter-manually" : (providerConfig ?? "")
  );

  const isGeneralError = providerError?.includes("No provider selected");
  const inputError =
    providerError && !isGeneralError ? providerError : undefined;
  const isSelectError = !!inputError && selectValue !== "enter-manually";

  const handleSelectChange = (value: string) => {
    setSelectValue(value);
    if (value === "enter-manually" || value === "add-new") {
      return;
    }
    updateProperty("config", value);
  };

  const getSelectIcon = () => {
    if (selectValue === "add-new") {
      return <PlusIcon className="size-4 mr-1.5" />;
    }
    if (selectValue === "enter-manually") {
      return <PencilIcon className="size-4 mr-1.5" />;
    }
    if (!providerType) {
      return <></>;
    }
    return (
      <DynamicImageProviderIcon
        providerType={providerType}
        width="24"
        height="24"
        className="mr-1.5"
      />
    );
  };

  if (!doesProviderNeedInstallation) {
    return (
      <section>
        <Callout color="teal" title="You're all set">
          <span className="capitalize">{providerType}</span> provider does not
          require installation
        </Callout>
      </section>
    );
  }

  return (
    <section>
      <div className="mb-2">
        <Text className="font-bold">Select provider</Text>
        {isGeneralError && (
          <Text className="text-red-500">{providerError}</Text>
        )}
      </div>
      <Select
        className="mb-1.5"
        placeholder="Select provider"
        value={selectValue}
        icon={getSelectIcon}
        onValueChange={handleSelectChange}
        error={isSelectError}
        errorMessage={inputError}
      >
        {installedProviderByType?.map((provider) => {
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
        })}
        <SelectItem
          icon={() => <PencilIcon className="mx-0.5 size-5 mr-1.5" />}
          value="enter-manually"
        >
          Manual provider name
        </SelectItem>
        {providerType && (
          <SelectItem
            icon={() => <PlusIcon className="mx-0.5 size-5 mr-1.5" />}
            value="add-new"
          >
            Add {providerObject?.display_name ?? providerType} provider
          </SelectItem>
        )}
      </Select>
      {/* TODO: replace with select with "create new" option */}
      {/* <p className="text-sm text-gray-500 text-center mb-1.5">or</p> */}
      {selectValue === "enter-manually" && (
        <>
          <Text className="mb-1.5">Enter provider name manually</Text>
          <TextInput
            placeholder="Enter provider name"
            onChange={(e: any) => updateProperty("config", e.target.value)}
            className="mb-2.5"
            value={providerConfig || ""}
            error={!!inputError}
            errorMessage={inputError}
            disabled={!doesProviderNeedInstallation}
          />
        </>
      )}
      {selectValue === "add-new" && providerType && (
        <InstallProviderButton providerType={providerType} />
      )}
    </section>
  );
}

function KeepStepEditor({
  properties,
  updateProperty,
  type,
  parametersError,
  variableError,
}: KeepEditorProps & {
  parametersError?: string | null;
  variableError?: string | null;
}) {
  const stepParams =
    ((type?.includes("step-")
      ? properties.stepParams
      : properties.actionParams) as string[]) ?? [];
  const existingParams = Object.keys((properties.with as object) ?? {});
  const params = [...stepParams, ...existingParams];
  const uniqueParams = params
    .filter((item, pos) => params.indexOf(item) === pos)
    .filter(
      (item) =>
        item !== "kwargs" &&
        item !== "enrich_alert" &&
        item !== "enrich_incident"
    );

  function handleWithKeyChange(e: any) {
    const currentWith = (properties.with as object) ?? {};
    updateProperty("with", { ...currentWith, [e.target.id]: e.target.value });
  }

  return (
    <div className="flex flex-col gap-2">
      <section className="flex flex-col gap-2">
        <div>
          <Text className="font-bold">Provider parameters</Text>
          {parametersError && (
            <Callout
              color="rose"
              className="text-sm my-1"
              title={parametersError}
            />
          )}
          {variableError && (
            <Callout
              color="yellow"
              className="text-sm my-1"
              title={variableError.split("-")[0]}
            >
              {variableError.split("-")[1]}
            </Callout>
          )}
          {uniqueParams.map((key) => {
            let currentPropertyValue = ((properties.with as any) ?? {})[key];
            const isJson = typeof currentPropertyValue === "object";
            if (isJson) {
              currentPropertyValue = JSON.stringify(
                currentPropertyValue,
                null,
                2
              );
            }
            return (
              <EditorField
                key={key}
                name={key}
                value={currentPropertyValue}
                onChange={handleWithKeyChange}
                asTextarea={isJson}
              />
            );
          })}
        </div>
        <div className="flex flex-col gap-2">
          <Text className="font-bold">Step parameters</Text>
          <div>
            <Text className="mb-1.5">If Condition</Text>
            <TextInput
              id="if"
              placeholder="If Condition"
              onValueChange={(value) => updateProperty("if", value)}
              className="mb-2.5"
              value={properties?.if || ("" as string)}
            />
          </div>
          <div>
            <Text className="capitalize mb-1.5">Variables</Text>
            <KeyValueListField
              keyValueList={Object.entries(properties.vars ?? {}).map(
                ([key, value]) => ({
                  key,
                  value: value as string,
                })
              )}
              onChange={(newList) => {
                updateProperty(
                  "vars",
                  newList.reduce((acc: any, item: any) => {
                    acc[item.key] = item.value;
                    return acc;
                  }, {})
                );
              }}
            />
          </div>
          {properties.with?.enrich_alert && (
            <div>
              <Text>Enrich Alert</Text>
              <Text className="text-sm text-gray-500 mb-2">
                Enrich alert with the following key-value pairs. Only works if
                alert trigger is enabled.
              </Text>
              <KeyValueListField
                keyValueList={properties.with.enrich_alert}
                onChange={(newList) => {
                  updateProperty("with", {
                    ...properties.with,
                    enrich_alert: newList,
                  });
                }}
              />
            </div>
          )}
          {properties.with?.enrich_incident && (
            <div>
              <Text>Enrich Incident</Text>
              <Text className="text-sm text-gray-500 mb-2">
                Enrich incident with the following key-value pairs. Only works
                if incident trigger is enabled.
              </Text>
              <KeyValueListField
                keyValueList={properties.with.enrich_incident}
                onChange={(newList) => {
                  updateProperty("with", {
                    ...properties.with,
                    enrich_incident: newList,
                  });
                }}
              />
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function KeepThresholdConditionEditor({
  properties,
  updateProperty,
  error,
}: {
  properties: V2StepConditionThreshold["properties"];
  updateProperty: (key: string, value: any) => void;
  error?: string | null;
}) {
  const currentValueValue = properties.value ?? "";
  const currentCompareToValue = properties.compare_to ?? "";
  return (
    <>
      {error && <Text className="text-red-500">{error}</Text>}
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
  error,
}: {
  properties: V2StepConditionAssert["properties"];
  updateProperty: (key: string, value: any) => void;
  error?: string | null;
}) {
  const currentAssertValue = properties.assert ?? "";
  return (
    <>
      <Text>Assert</Text>
      <TextInput
        placeholder="E.g. 200 == 200"
        onChange={(e: any) => updateProperty("assert", e.target.value)}
        className="mb-2.5"
        value={currentAssertValue}
        error={!!error}
        errorMessage={error ?? undefined}
      />
    </>
  );
}

function KeepForeachEditor({
  properties,
  updateProperty,
  error,
}: {
  properties: V2StepForeach["properties"];
  updateProperty: (key: string, value: any) => void;
  error?: string | null;
}) {
  const currentValueValue = properties.value ?? "";

  return (
    <>
      <Text>Foreach Value</Text>
      <TextInput
        placeholder="Value"
        onChange={(e: any) => updateProperty("value", e.target.value)}
        className="mb-2.5"
        value={currentValueValue}
        error={!!error}
        errorMessage={error ?? undefined}
      />
    </>
  );
}

type ActionOrStepProperties =
  | V2StepStep["properties"]
  | V2ActionStep["properties"];

export function StepEditorV2() {
  const { selectedNode, getNodeById } = useWorkflowStore();
  const nodeData = useMemo(() => {
    if (!selectedNode) {
      return null;
    }
    const node = getNodeById(selectedNode);
    if (
      !node ||
      node.data.componentType === "condition-assert__end" ||
      node.data.componentType === "condition-threshold__end"
    ) {
      return null;
    }

    const parsedNode = NodeDataStepSchema.parse(node.data);
    return {
      type: parsedNode.type,
      componentType: parsedNode.componentType,
      name: parsedNode.name,
      properties: parsedNode.properties,
    };
  }, [selectedNode]);

  if (!nodeData) {
    // If the node is not a step, action, condition or foreach, don't render anything
    return null;
  }

  if (
    nodeData.componentType === "switch" &&
    nodeData.type === "condition-threshold"
  ) {
    return (
      <ConditionsAndMiscEditor
        initialFormData={{
          type: "condition-threshold",
          name: nodeData.name,
          properties:
            nodeData.properties as V2StepConditionThreshold["properties"],
        }}
      />
    );
  }

  if (
    nodeData.componentType === "switch" &&
    nodeData.type === "condition-assert"
  ) {
    return (
      <ConditionsAndMiscEditor
        initialFormData={{
          type: "condition-assert",
          name: nodeData.name,
          properties:
            nodeData.properties as V2StepConditionAssert["properties"],
        }}
      />
    );
  }
  if (nodeData.componentType === "container") {
    return (
      <ConditionsAndMiscEditor
        initialFormData={{
          type: nodeData.type as "foreach",
          name: nodeData.name,
          properties: nodeData.properties as V2StepForeach["properties"],
        }}
      />
    );
  }
  return (
    <ActionOrStepEditor
      initialFormData={{
        type: nodeData.type,
        name: nodeData.name,
        properties: nodeData.properties as ActionOrStepProperties,
      }}
    />
  );
}

type ConditionsAndMiscFormDataType =
  | {
      type: "condition-threshold";
      name: string;
      properties: V2StepConditionThreshold["properties"];
    }
  | {
      type: "condition-assert";
      name: string;
      properties: V2StepConditionAssert["properties"];
    }
  | {
      type: "foreach";
      name: string;
      properties: V2StepForeach["properties"];
    };

function ConditionsAndMiscEditor({
  initialFormData,
}: {
  initialFormData: ConditionsAndMiscFormDataType;
}) {
  const [formData, setFormData] = useState(initialFormData);
  const { updateSelectedNodeData, setEditorSynced, validationErrors } =
    useWorkflowStore();
  const error = validationErrors?.[formData.name || ""];
  const saveFormDataToStoreDebounced = useCallback(
    debounce((formData: any) => {
      updateSelectedNodeData("name", formData.name);
      updateSelectedNodeData("properties", formData.properties);
    }, 300),
    [updateSelectedNodeData]
  );
  const handlePropertyChange = (key: string, value: any) => {
    const updatedFormData = {
      ...formData,
      properties: {
        ...formData.properties,
        [key]: value,
      },
    };
    setFormData(updatedFormData as ConditionsAndMiscFormDataType);
    setEditorSynced(false);
    saveFormDataToStoreDebounced(updatedFormData);
  };
  return (
    <EditorLayout className="flex-1">
      {formData.type === "condition-threshold" ? (
        <KeepThresholdConditionEditor
          properties={formData.properties}
          updateProperty={handlePropertyChange}
          error={error}
        />
      ) : formData.type === "foreach" ? (
        <KeepForeachEditor
          properties={formData.properties}
          updateProperty={handlePropertyChange}
          error={error}
        />
      ) : formData.type === "condition-assert" ? (
        <KeepAssertConditionEditor
          properties={formData.properties}
          updateProperty={handlePropertyChange}
          error={error}
        />
      ) : null}
    </EditorLayout>
  );
}

type ActionOrStepFormDataType = {
  type: string;
  name?: string;
  properties: ActionOrStepProperties;
};

function ActionOrStepEditor({
  initialFormData,
}: {
  initialFormData: ActionOrStepFormDataType;
}) {
  const [formData, setFormData] =
    useState<ActionOrStepFormDataType>(initialFormData);
  const {
    updateSelectedNodeData,
    setEditorSynced,
    triggerSave,
    validationErrors,
    isEditorSyncedWithNodes,
    isSaving,
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
    const updatedFormData = { ...formData, [e.target.name]: e.target.value };
    setFormData(updatedFormData);
    setEditorSynced(false);
    saveFormDataToStoreDebounced(updatedFormData);
  };

  const handlePropertyChange = (key: string, value: any) => {
    const updatedFormData = {
      ...formData,
      properties: {
        ...formData.properties,
        [key]: value,
      } as ActionOrStepProperties,
    };
    setFormData(updatedFormData);
    setEditorSynced(false);
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
  let variableError = null;
  if (error?.includes("parameters")) {
    parametersError = error;
  }

  if (error?.includes("provider")) {
    providerError = error;
  }

  if (error?.startsWith("Variable:")) {
    variableError = error;
  }

  const { data: { installed_providers: installedProviders } = {} } =
    useProviders();

  const providerObject = installedProviders?.find(
    (p) => p.type === providerType
  );

  const method = formData.type?.includes("step-") ? "_query" : "_notify";
  const methodParams = formData.properties?.with ?? {};
  const providerConfig =
    providerObject && !checkProviderNeedsInstallation(providerObject)
      ? "default-" + providerType
      : (formData.properties?.config ?? "")?.trim();

  const installedProvider = installedProviders?.find(
    (p) => p.type === providerType && p.details?.name === providerConfig
  );
  const providerId = installedProvider?.id;

  const defaultTabIndex = providerError ? 0 : parametersError ? 1 : 1;

  const [tabIndex, setTabIndex] = useState(defaultTabIndex);

  const handleTabChange = (index: number) => {
    setTabIndex(index);
  };

  const saveButtonDisabled = !isEditorSyncedWithNodes || isSaving;
  const saveButtonText = isSaving ? "Saving..." : "Save & Continue";

  const setupStatus = () => {
    if (providerError) {
      return "error";
    }
    return "ok";
  };

  const configureStatus = () => {
    if (parametersError) {
      return "error";
    }
    if (
      formData.properties?.with &&
      Object.keys(formData.properties?.with).length > 0
    ) {
      return "ok";
    }
    return "neutral";
  };

  const getStepIcon = (status: "error" | "ok" | "neutral") => {
    if (status === "error") {
      return <ExclamationCircleIcon className="size-4 text-red-500" />;
    }
    if (status === "ok") {
      return <CheckCircleIcon className="size-4" />;
    }
    return null;
  };

  return (
    <TabGroup
      index={tabIndex}
      onIndexChange={handleTabChange}
      className="flex-1 flex flex-col"
    >
      <div className="pt-2.5 px-4">
        <Subtitle className="font-medium capitalize">
          {providerType} {formData.type.split("-")[0]}
        </Subtitle>
        <Text className="mt-1">Unique Identifier</Text>
        <TextInput
          className="mb-2.5"
          icon={KeyIcon}
          name="name"
          value={formData.name || ""}
          onChange={handleInputChange}
        />
      </div>
      <TabList className="px-4">
        <Tab value="select">
          <div className="flex items-center gap-1">
            Setup {getStepIcon(setupStatus())}
          </div>
        </Tab>
        <Tab value="configure">
          <div className="flex items-center gap-1">
            Configure {getStepIcon(configureStatus())}
          </div>
        </Tab>
        <Tab value="test">Test</Tab>
      </TabList>
      <TabPanels className="flex-1 flex flex-col">
        <TabPanel className="flex-1">
          <div className="h-full flex flex-col">
            <EditorLayout className="flex-1">
              {type && formData.properties ? (
                <KeepSetupProviderEditor
                  providerType={providerType}
                  providerError={providerError}
                  properties={formData.properties}
                  updateProperty={handlePropertyChange}
                />
              ) : null}
            </EditorLayout>
            <div className="sticky flex justify-end bottom-0 px-4 py-2.5 bg-white border-t border-gray-200">
              <Button
                variant="primary"
                color="orange"
                className="w-full disabled:opacity-70"
                onClick={() => {
                  handleSubmit();
                  setTabIndex(1);
                }}
                data-testid="wf-editor-setup-save-button"
                disabled={saveButtonDisabled}
              >
                {saveButtonText}
              </Button>
            </div>
          </div>
        </TabPanel>
        <TabPanel className="flex-1">
          <div className="h-full flex flex-col">
            <EditorLayout className="flex-1">
              {type && formData.properties ? (
                <KeepStepEditor
                  parametersError={parametersError}
                  variableError={variableError}
                  properties={formData.properties}
                  updateProperty={handlePropertyChange}
                  providerType={providerType}
                  type={formData.type}
                />
              ) : null}
            </EditorLayout>
            <div className="sticky flex justify-end bottom-0 px-4 py-2.5 bg-white border-t border-gray-200">
              <Button
                variant="primary"
                color="orange"
                className="w-full disabled:opacity-70"
                onClick={() => {
                  handleSubmit();
                  setTabIndex(2);
                }}
                data-testid="wf-editor-configure-save-button"
                disabled={saveButtonDisabled}
              >
                {saveButtonText}
              </Button>
            </div>
          </div>
        </TabPanel>
        <TabPanel className="flex-1">
          <TestRunStepForm
            providerInfo={{
              provider_id: providerId || providerConfig || "",
              provider_type: providerType ?? "",
            }}
            method={method}
            methodParams={methodParams}
          />
        </TabPanel>
      </TabPanels>
    </TabGroup>
  );
}
