import {
  useStepEditor,
  useGlobalEditor,
} from "sequential-workflow-designer-react";

export function GlobalEditor() {
  const { properties, setProperty } = useGlobalEditor();
  return <h3>Welcome!</h3>;
}

export default function StepEditor() {
  const { type, componentType, name, setName, properties, setProperty } =
    useStepEditor();

  function onNameChanged(e: any) {
    setName(e.target.value);
  }

  return (
    <>
      <h3>Name</h3>
      <input value={name} onChange={onNameChanged} />
      <h3>Type</h3>
      <p>{type}</p>
      <h2>Properties</h2>
      <pre>{JSON.stringify(properties, null, 2)}</pre>
    </>
  );
}
