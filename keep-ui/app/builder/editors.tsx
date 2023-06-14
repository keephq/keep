import { Title, Text, TextInput } from "@tremor/react";
import { KeyIcon } from "@heroicons/react/20/solid";
import { Properties } from "sequential-workflow-designer";
import {
  useStepEditor,
  useGlobalEditor,
} from "sequential-workflow-designer-react";

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
        alerts YAML specification.
      </Text>
      <Text className="mt-5">
        Use the toolbox to add steps, conditions and actions to your workflow
        and click the `Generate` button to compile the alert.
      </Text>
    </EditorLayout>
  );
}

interface keepEditorProps {
  properties: Properties;
  updateProperty: (key: string, value: any) => void;
}

function KeepStepEditor({ properties, updateProperty }: keepEditorProps) {
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

  const providerConfig = (properties.config as string) ?? "";

  return (
    <>
      <Text>Provider Config</Text>
      <TextInput
        placeholder="E.g. {{ providers.provider-id }}"
        onChange={(e: any) => updateProperty("config", e.target.value)}
        className="mb-2.5"
        value={providerConfig}
      />
      {uniqueParams?.map((key) => {
        let currentPropertyValue = ((properties.with as any) ?? {})[key];
        if (typeof currentPropertyValue === "object") {
          currentPropertyValue = JSON.stringify(currentPropertyValue);
        }
        const randomKey = `${key}-${Math.floor(Math.random() * 1000)}`;
        return (
          <>
            <Text key={`text-${randomKey}`}>{key}</Text>
            <TextInput
              id={`${key}`}
              key={`${randomKey}`}
              placeholder={key}
              onChange={propertyChanged}
              className="mb-2.5"
              value={currentPropertyValue ?? ""}
            />
          </>
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

export default function StepEditor() {
  const { type, componentType, name, setName, properties, setProperty } =
    useStepEditor();

  function onNameChanged(e: any) {
    setName(e.target.value);
  }

  const keepType = type.split("-")[1] as "action" | "step" | "condition";

  return (
    <EditorLayout>
      <Title>{keepType} Editor</Title>
      <Text>Name</Text>
      <TextInput
        className="mb-2.5"
        icon={KeyIcon}
        value={name}
        onChange={onNameChanged}
      />
      {type.includes("step-") || type.includes("action-") ? (
        <KeepStepEditor properties={properties} updateProperty={setProperty} />
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
