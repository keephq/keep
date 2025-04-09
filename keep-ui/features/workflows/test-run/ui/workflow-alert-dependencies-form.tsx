import { useMemo, useState } from "react";
import { Button, Subtitle, Text, Title } from "@tremor/react";
import { TextInput } from "@/components/ui";
import { PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import { JsonCard } from "@/shared/ui/JsonCard";

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

const getAlertPayload = (
  dynamicFields: Field[],
  dependencyValues: Record<string, string>,
  staticFields: Field[]
) => {
  // Construct payload with a flexible structure
  const payload: Payload = dynamicFields.reduce((acc, field) => {
    if (field.key) {
      buildNestedObject(acc, field.key, field.value);
    }
    return acc;
  }, {});

  // Merge dependencyValues into the payload
  Object.keys(dependencyValues).forEach((key) => {
    buildNestedObject(payload, key, dependencyValues[key]);
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

interface WorkflowAlertDependenciesFormProps {
  dependencies: string[];
  staticFields: Field[];
  onCancel: () => void;
  onSubmit: (payload: Payload) => void;
}

export function WorkflowAlertDependenciesForm({
  dependencies,
  staticFields,
  onCancel,
  onSubmit,
}: WorkflowAlertDependenciesFormProps) {
  const [dynamicFields, setDynamicFields] = useState<Field[]>([]);
  const [fieldErrors, setFieldErrors] = useState(
    new Array(dynamicFields.length).fill({ key: false, value: false })
  );
  const [dependenciesErrors, setDependenciesErrors] = useState(
    new Array(dependencies.length).fill(false)
  );
  const [dependencyValues, setDependencyValues] = useState<
    Record<string, string>
  >({});

  const validateDynamicFields = (newDynamicFields: Field[]) => {
    // verify all fields are filled
    return newDynamicFields.map((field) => ({
      key: !field.key,
      value: !field.value,
    }));
  };

  const validateDependencies = (
    dependencies: string[],
    newDependencyValues: Record<string, string>
  ) => {
    // Verify dependencies have values
    return dependencies.map((dep) => !newDependencyValues[dep]);
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
    setFieldErrors(validateDynamicFields(newDynamicFields));
  };

  const handleDependencyChange = (dependencyName: string, newValue: string) => {
    const newDependencyValues = {
      ...dependencyValues,
      [dependencyName]: newValue,
    };
    setDependencyValues(newDependencyValues);
    setDependenciesErrors(
      validateDependencies(dependencies, newDependencyValues)
    );
  };

  const handleDeleteField = (index: number) => {
    const newDynamicFields = dynamicFields.filter((_, i) => i !== index);
    setDynamicFields(newDynamicFields);
    setFieldErrors(validateDynamicFields(newDynamicFields));
  };

  const handleAddField = (e: React.FormEvent) => {
    e.preventDefault();
    setDynamicFields([...dynamicFields, { key: "", value: "" }]);
    setFieldErrors(validateDynamicFields(dynamicFields));
  };

  const payload = useMemo(() => {
    return getAlertPayload(dynamicFields, dependencyValues, staticFields);
  }, [dynamicFields, dependencyValues, staticFields]);

  const isValid = useMemo(() => {
    return (
      fieldErrors.every((error) => !error.key && !error.value) &&
      dependenciesErrors.every((error) => !error)
    );
  }, [fieldErrors, dependenciesErrors]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const dynamicFieldErrors = validateDynamicFields(dynamicFields);
    const dependenciesErrors = validateDependencies(
      dependencies,
      dependencyValues
    );
    setFieldErrors(dynamicFieldErrors);
    setDependenciesErrors(dependenciesErrors);
    const isValid =
      dynamicFieldErrors.every((error) => !error.key && !error.value) &&
      dependenciesErrors.every((error) => !error);
    if (!isValid) {
      return;
    }
    const payload = getAlertPayload(
      dynamicFields,
      dependencyValues,
      staticFields
    );
    onSubmit(payload);
  };

  const keyClassName = "w-2/6 font-mono";
  const valueClassName = "flex-1 font-mono";

  return (
    <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
      <header>
        <Subtitle>Build Alert Payload</Subtitle>
        <Text>Enter values required to run the workflow</Text>
      </header>
      {Array.isArray(staticFields) && staticFields.length > 0 && (
        <section>
          <Text className="mb-2">Fields defined in alert trigger filters</Text>
          {staticFields.map((field, index) => (
            <div key={field.key} className="flex gap-2 mb-2">
              <TextInput
                placeholder="key"
                value={field.key}
                className={keyClassName}
                disabled
              />
              <TextInput
                placeholder="value"
                value={field.value}
                className={valueClassName}
                disabled
              />
            </div>
          ))}
        </section>
      )}

      <section>
        <Text className="mb-2">Alert fields used in the workflow</Text>
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
                placeholder="value"
                value={dependencyValues[dependencyName] || ""}
                onChange={(e) =>
                  handleDependencyChange(dependencyName, e.target.value)
                }
                error={dependenciesErrors[index]}
                className={valueClassName}
              />
            </div>
          ))}
        {dynamicFields.map((field, index) => (
          <div key={index} className="flex items-center gap-2 mb-2">
            <TextInput
              placeholder="key"
              value={field.key}
              className={keyClassName}
              onChange={(e) => handleFieldChange(index, "key", e.target.value)}
              error={fieldErrors[index]?.key}
            />
            <TextInput
              placeholder="value"
              value={field.value}
              className={valueClassName}
              onChange={(e) =>
                handleFieldChange(index, "value", e.target.value)
              }
              error={fieldErrors[index]?.value}
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
      </section>
      {payload && <JsonCard title="alertPayload" json={payload} />}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" color="orange" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="submit"
          variant="primary"
          color="orange"
          disabled={!isValid}
        >
          Test Run
        </Button>
      </div>
    </form>
  );
}
