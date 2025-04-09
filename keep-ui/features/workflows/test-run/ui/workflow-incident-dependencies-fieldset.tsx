import { useEffect, useState } from "react";
import { Button, Text, Subtitle } from "@tremor/react";
import { TextInput } from "@/components/ui";
import { PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";

function buildNestedObject(
  acc: Record<string, any>,
  key: string,
  value: string
) {
  const keys = key.split(".");
  let current = acc;

  for (let i = 0; i < keys.length - 1; i++) {
    const part = keys[i];
    current[part] = current[part] || {};
    current = current[part];
  }

  current[keys[keys.length - 1]] = value;
  return acc;
}

const getIncidentPayload = (
  dynamicFields: Field[],
  dependencyValues: Record<string, string>,
  staticFields: Field[] = []
) => {
  // Construct payload with a flexible structure
  const payload: Payload = dynamicFields.reduce((acc, field) => {
    if (field.key && field.value) {
      buildNestedObject(acc, field.key, field.value);
    }
    return acc;
  }, {});

  // Merge dependencyValues into the payload
  Object.keys(dependencyValues).forEach((key) => {
    if (dependencyValues[key]) {
      buildNestedObject(payload, key, dependencyValues[key]);
    }
  });

  // Add staticFields to the payload
  staticFields.forEach((field) => {
    buildNestedObject(payload, field.key, field.value);
  });

  // Add fingerprint key with a random number
  const randomNum = Math.floor(Math.random() * 1000000);
  payload["fingerprint"] = `test-workflow-fingerprint-${randomNum}`;

  return payload;
};

interface Field {
  key: string;
  value: string;
}

type Payload = Record<string, any>;

interface WorkflowIncidentDependenciesFieldsetProps {
  dependencies: string[];
  onPayloadChange: (payload: Payload | null) => void;
}

export function WorkflowIncidentDependenciesFieldset({
  dependencies,
  onPayloadChange,
}: WorkflowIncidentDependenciesFieldsetProps) {
  const [dynamicFields, setDynamicFields] = useState<Field[]>([]);
  const [fieldErrors, setFieldErrors] = useState(
    new Array(dynamicFields.length).fill(false)
  );
  const [dependenciesErrors, setDependenciesErrors] = useState(
    new Array(dependencies.length).fill(false)
  );
  const [dependencyValues, setDependencyValues] = useState<
    Record<string, string>
  >({});

  const validateDynamicFields = () => {
    // verify all fields are filled
    const dynamicFieldErrors = dynamicFields.map(
      (field) => !field.key || !field.value
    );
    setFieldErrors(dynamicFieldErrors);
  };

  const validateDependencies = () => {
    // Verify dependencies have values
    const newDependenciesErrors = dependencies.map(
      (dep) => !dependencyValues[dep]
    );
    setDependenciesErrors(newDependenciesErrors);
  };

  const handleFieldChange = (
    index: number,
    keyOrValue: string,
    newValue: string
  ) => {
    const newDynamicFields = dynamicFields.map((field, i) => {
      if (i === index) {
        return { ...field, [keyOrValue]: newValue };
      }
      return field;
    });
    setDynamicFields(newDynamicFields);
    validateDynamicFields();
  };

  const handleDependencyChange = (dependencyName: string, newValue: string) => {
    const newDependencyValues = {
      ...dependencyValues,
      [dependencyName]: newValue,
    };
    setDependencyValues(newDependencyValues);
    validateDependencies();
  };

  const handleDeleteField = (index: number) => {
    const newDynamicFields = dynamicFields.filter((_, i) => i !== index);
    setDynamicFields(newDynamicFields);
    validateDynamicFields();
  };

  const handleAddField = (e: React.FormEvent) => {
    e.preventDefault();
    setDynamicFields([...dynamicFields, { key: "", value: "" }]);
    validateDynamicFields();
  };

  useEffect(
    function onChange() {
      onPayloadChange(getIncidentPayload(dynamicFields, dependencyValues));
    },
    [dynamicFields, dependencyValues]
  );

  const keyClassName = "w-2/6";
  const valueClassName = "flex-1";

  return (
    <fieldset>
      <Subtitle className="mb-2">Incident</Subtitle>
      <section className="mb-4">
        <Text className="mb-2">Required Incident Fields</Text>
        {Array.isArray(dependencies) &&
          dependencies.map((dependencyName, index) => (
            <div key={dependencyName} className="flex gap-2 mb-2">
              <TextInput
                placeholder={dependencyName}
                value={dependencyName}
                className={keyClassName}
                disabled
              />
              <TextInput
                placeholder="Value"
                value={dependencyValues[dependencyName] || ""}
                onChange={(e) =>
                  handleDependencyChange(dependencyName, e.target.value)
                }
                error={dependenciesErrors[index]}
                className={valueClassName}
              />
            </div>
          ))}
      </section>
      {dynamicFields.map((field, index) => (
        <div
          key={index}
          className={clsx(
            "flex items-center gap-2 mb-2",
            fieldErrors[index] ? "border-2 border-red-500 p-2" : ""
          )}
        >
          <TextInput
            placeholder="Key"
            value={field.key}
            className={keyClassName}
            onChange={(e) => handleFieldChange(index, "key", e.target.value)}
          />
          <TextInput
            placeholder="Value"
            value={field.value}
            className={valueClassName}
            onChange={(e) => handleFieldChange(index, "value", e.target.value)}
          />
          <button
            onClick={() => handleDeleteField(index)}
            className="flex items-center text-gray-500 hover:text-gray-700"
          >
            <TrashIcon className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      ))}
      <div className="flex justify-end">
        <Button
          variant="light"
          icon={PlusIcon}
          color="orange"
          onClick={handleAddField}
        >
          Add another field
        </Button>
      </div>
    </fieldset>
  );
}
