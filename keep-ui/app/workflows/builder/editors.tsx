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
import { Properties } from "sequential-workflow-designer";
import {
  useStepEditor,
  useGlobalEditor,
} from "sequential-workflow-designer-react";
import { Provider } from "app/providers/providers";
import {
  BackspaceIcon,
  BellSnoozeIcon,
  ClockIcon,
  FunnelIcon,
  HandRaisedIcon,
} from "@heroicons/react/24/outline";

function EditorLayout({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col m-2.5">{children}</div>;
}

export function GlobalEditor() {
  const { properties, setProperty } = useGlobalEditor();
  return (
    <EditorLayout>
      <Title>Keep Workflow Editor</Title>
      <Text>
        Use this visual workflow editor to easily create or edit existing Keep
        workflow YAML specifications.
      </Text>
      <Text className="mt-5">
        Use the toolbox to add steps, conditions and actions to your workflow
        and click the `Generate` button to compile the workflow / `Deploy`
        button to deploy the workflow to Keep.
      </Text>
      {WorkflowEditor(properties, setProperty)}
    </EditorLayout>
  );
}

interface keepEditorProps {
  properties: Properties;
  updateProperty: (key: string, value: any) => void;
  installedProviders?: Provider[] | null | undefined;
  providerType?: string;
}

function KeepStepEditor({
  properties,
  updateProperty,
  installedProviders,
  providerType,
}: keepEditorProps) {
  const stepParams = (properties.stepParams ??
    properties.actionParams ??
    []) as string[];
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

function WorkflowEditor(properties: Properties, updateProperty: any) {
  /**
   * TODO: support generate, add more triggers and complex filters
   *  Need to think about UX for this
   */
  const propertyKeys = Object.keys(properties).filter(
    (k) => k !== "isLocked" && k !== "id"
  );

  const updateAlertFilter = (filter: string, value: string) => {
    const currentFilters = properties.alert as {};
    const updatedFilters = { ...currentFilters, [filter]: value };
    updateProperty("alert", updatedFilters);
  };

  const addFilter = () => {
    const filterName = prompt("Enter filter name");
    if (filterName) {
      updateAlertFilter(filterName, "");
    }
  };

  const addTrigger = (trigger: "manual" | "interval" | "alert") => {
    updateProperty(
      trigger,
      trigger === "alert" ? { source: "" } : trigger === "manual" ? "true" : ""
    );
  };

  const deleteFilter = (filter: string) => {
    const currentFilters = properties.alert as any;
    delete currentFilters[filter];
    updateProperty("alert", currentFilters);
  };

  return (
    <>
      <Title className="mt-2.5">Workflow Settings</Title>
      <div className="w-1/2">
        {Object.keys(properties).includes("manual") ? null : (
          <Button
            onClick={() => addTrigger("manual")}
            className="mb-1"
            size="xs"
            color="orange"
            variant="light"
            icon={HandRaisedIcon}
          >
            Add Manual Trigger
          </Button>
        )}
        {Object.keys(properties).includes("interval") ? null : (
          <Button
            onClick={() => addTrigger("interval")}
            className="mb-1"
            size="xs"
            color="orange"
            variant="light"
            icon={ClockIcon}
          >
            Add Interval Trigger
          </Button>
        )}
        {Object.keys(properties).includes("alert") ? null : (
          <Button
            onClick={() => addTrigger("alert")}
            className="mb-1"
            size="xs"
            color="orange"
            variant="light"
            icon={BellSnoozeIcon}
          >
            Add Alert Trigger
          </Button>
        )}
      </div>
      {propertyKeys.map((key, index) => {
        return (
          <div key={index}>
            <Text className="capitalize mt-2.5">{key}</Text>
            {key === "manual" ? (
              <div key={key}>
                <input
                  type="checkbox"
                  checked={properties[key] === "true"}
                  onChange={(e) =>
                    updateProperty(key, e.target.checked ? "true" : "false")
                  }
                />
              </div>
            ) : key === "alert" ? (
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
                {properties.alert && Object.keys(properties.alert as {}).map((filter) => {
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
            ) : (
              <TextInput
                placeholder={`Set the ${key}`}
                onChange={(e: any) => updateProperty(key, e.target.value)}
                value={properties[key] as string}
              />
            )}
          </div>
        );
      })}
    </>
  );
}

export default function StepEditor({
  installedProviders,
}: {
  installedProviders?: Provider[] | undefined | null;
}) {
  const { type, componentType, name, setName, properties, setProperty } =
    useStepEditor();

  function onNameChanged(e: any) {
    setName(e.target.value);
  }

  const providerType = type.split("-")[1];

  return (
    <EditorLayout>
      <Title className="capitalize">{providerType} Editor</Title>
      <Text className="mt-1">Unique Identifier</Text>
      <TextInput
        className="mb-2.5"
        icon={KeyIcon}
        value={name}
        onChange={onNameChanged}
      />
      {type.includes("step-") || type.includes("action-") ? (
        <KeepStepEditor
          properties={properties}
          updateProperty={setProperty}
          installedProviders={installedProviders}
          providerType={providerType}
        />
      ) : type === "condition-threshold" ? (
        <KeepThresholdConditionEditor
          properties={properties}
          updateProperty={setProperty}
        />
      ) : type.includes("foreach") ? (
        <KeepForeachEditor
          properties={properties}
          updateProperty={setProperty}
        />
      ) : type === "condition-assert" ? (
        <KeepAssertConditionEditor
          properties={properties}
          updateProperty={setProperty}
        />
      ) : null}
    </EditorLayout>
  );
}
