import {
  Button,
  Icon,
  Select,
  SelectItem,
  Subtitle,
  Text,
} from "@tremor/react";
import { KeyIcon } from "@heroicons/react/20/solid";
import { Provider } from "@/app/(keep)/providers/providers";
import { BackspaceIcon, PlusIcon } from "@heroicons/react/24/outline";
import React, { useCallback, useState } from "react";
import { useWorkflowStore } from "@/entities/workflows";
import { V2Properties } from "@/entities/workflows/model/types";
import { DynamicImageProviderIcon, TextInput } from "@/components/ui";
import debounce from "lodash.debounce";
import { StepTestRunButton } from "../StepTestRunButton";
import { PROVIDERS_WITH_NO_CONFIG } from "@/entities/workflows/model/validation";
import { EditorField } from "@/features/workflows/builder/ui/Editor/EditorField";
import { useProviders } from "@/utils/hooks/useProviders";

export function EditorLayout({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col mx-4 my-2.5">{children}</div>;
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

function getProviderConfig(
  providerType: string | undefined,
  properties: V2Properties
) {
  const providerConfig = (properties.config as string)?.trim();
  if (PROVIDERS_WITH_NO_CONFIG.includes(providerType ?? "")) {
    return "default-" + providerType;
  }
  if (!providerConfig) {
    return null;
  }
  return providerConfig;
}

function validateProviderConfig(
  providerType: string | undefined,
  providerConfig: string,
  providers: Provider[] | null | undefined,
  installedProviders: Provider[] | null | undefined
) {
  if (PROVIDERS_WITH_NO_CONFIG.includes(providerType ?? "")) {
    return "";
  }
  const isThisProviderNeedsInstallation =
    providers?.some(
      (p) =>
        p.type === providerType && p.config && Object.keys(p.config).length > 0
    ) ?? false;

  if (
    providerConfig &&
    isThisProviderNeedsInstallation &&
    installedProviders?.find(
      (p) => (p.type === providerType && p.details?.name) === providerConfig
    ) === undefined
  ) {
    return "This provider is not installed and you'll need to install it before executing this workflow.";
  }
  return "";
}

function KeepStepEditor({
  properties,
  updateProperty,
  providerType,
  type,
  providerError,
  parametersError,
}: KeepEditorProps & {
  providerError?: string | null;
  parametersError?: string | null;
}) {
  const { data: { providers, installed_providers: installedProviders } = {} } =
    useProviders();

  const stepParams =
    ((type?.includes("step-")
      ? properties.stepParams
      : properties.actionParams) as string[]) ?? [];
  const existingParams = Object.keys((properties.with as object) ?? {});
  const params = [...stepParams, ...existingParams];
  const uniqueParams = params
    .filter((item, pos) => params.indexOf(item) === pos)
    .filter((item) => item !== "kwargs");

  function propertyChanged(e: any) {
    const currentWith = (properties.with as object) ?? {};
    updateProperty("with", { ...currentWith, [e.target.id]: e.target.value });
  }

  const installedProviderByType = installedProviders?.filter(
    (p) => p.type === providerType
  );
  const providerConfig = getProviderConfig(providerType, properties);

  const providerNameError = validateProviderConfig(
    providerType,
    providerConfig ?? "",
    providers,
    installedProviders
  );

  const method = type?.includes("step-") ? "_query" : "_notify";
  const methodParams = properties.with ?? {};

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
            installedProviderByType?.length === 0 ||
            !installedProviderByType ||
            PROVIDERS_WITH_NO_CONFIG.includes(providerType ?? "")
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
          disabled={PROVIDERS_WITH_NO_CONFIG.includes(providerType ?? "")}
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
        {uniqueParams.map((key) => {
          let currentPropertyValue = ((properties.with as any) ?? {})[key];
          if (typeof currentPropertyValue === "object") {
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
              onChange={propertyChanged}
            />
          );
        })}
      </section>
      <StepTestRunButton
        providerInfo={{
          provider_id: providerConfig ?? "",
          provider_type: providerType ?? "",
        }}
        method={method}
        methodParams={methodParams}
        updateProperty={propertyChanged}
      />
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

export function StepEditorV2({
  initialFormData,
}: {
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
      <Subtitle className="font-medium capitalize">
        {providerType} Editor
      </Subtitle>
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
        className="sticky bottom-2.5 mt-2.5"
        onClick={handleSubmit}
        data-testid="wf-editor-save-deploy-button"
        disabled={!synced}
      >
        Save & Deploy
      </Button>
    </EditorLayout>
  );
}
