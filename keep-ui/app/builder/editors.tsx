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

  return (
    <div>
      {uniqueParams?.map((key) => {
        return (
          <>
            <Text id={`text-${key}`}>{key}</Text>
            <TextInput
              id={`input-${key}`}
              key={key}
              placeholder={key}
              onChange={propertyChanged}
              className="mb-2.5"
              value={((properties.with as any) ?? {})[key] ?? ""}
            />
          </>
        );
      })}
    </div>
  );
}

export default function StepEditor() {
  const { type, componentType, name, setName, properties, setProperty } =
    useStepEditor();

  function onNameChanged(e: any) {
    setName(e.target.value);
  }

  const keepType = type.split("-")[1];

  return keepType ? (
    <EditorLayout>
      <Title>Step Editor ({keepType})</Title>
      <Text>Name</Text>
      <TextInput
        className="mb-2.5"
        icon={KeyIcon}
        value={name}
        onChange={onNameChanged}
      />
      {type.includes("step-") || type.includes("action-") ? (
        <KeepStepEditor properties={properties} updateProperty={setProperty} />
      ) : null}
    </EditorLayout>
  ) : null;
}
