import { useStepEditor } from "sequential-workflow-designer-react";

function StepEditor() {
  const { type, componentType, name, setName, properties, setProperty } =
    useStepEditor();

  function onNameChanged(e: any) {
    setName(e.target.value);
  }

  function onProviderChange(e: any) {
    setProperty("providerType", e.target.value);
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

export default StepEditor;
