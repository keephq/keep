import { Title } from "@tremor/react";
import {
  useStepEditor,
  useGlobalEditor,
} from "sequential-workflow-designer-react";

export function GlobalEditor() {
  const { properties, setProperty } = useGlobalEditor();
  return <Title>Global Editor!</Title>;
}

export default function StepEditor() {
  const { type, componentType, name, setName, properties, setProperty } =
    useStepEditor();

  function onNameChanged(e: any) {
    setName(e.target.value);
  }

  return (
    <>
      <Title>Step Editor</Title>
      <h3>Name</h3>
      <input value={name} onChange={onNameChanged} />
      <h3>Type</h3>
      <p>{type}</p>
      <h2>Properties</h2>
      <pre>{JSON.stringify(properties, null, 2)}</pre>
    </>
  );
}
