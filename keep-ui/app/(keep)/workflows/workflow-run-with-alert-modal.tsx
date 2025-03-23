import { useState } from "react";
import { TextInput, Button, Text } from "@tremor/react";
import { PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import Modal from "@/components/ui/Modal";

interface StaticField {
  key: string;
  value: string;
}

interface AlertTriggerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: any) => void;
  staticFields?: StaticField[];
  dependencies?: string[];
}

interface Field {
  key: string;
  value: string;
}

export default function AlertTriggerModal({
  isOpen,
  onClose,
  onSubmit,
  staticFields = [],
  dependencies = [],
}: AlertTriggerModalProps) {
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
  };

  const handleDependencyChange = (dependencyName: string, newValue: string) => {
    const newDependencyValues = {
      ...dependencyValues,
      [dependencyName]: newValue,
    };
    setDependencyValues(newDependencyValues);

    // Update dependencies errors
    const newDependenciesErrors = dependencies.map(
      (dep) => !newDependencyValues[dep]
    );
    setDependenciesErrors(newDependenciesErrors);
  };

  const handleDeleteField = (index: number) => {
    const newDynamicFields = dynamicFields.filter((_, i) => i !== index);
    setDynamicFields(newDynamicFields);
    setFieldErrors((newFieldErrors) =>
      newFieldErrors.filter((_, i) => i !== index)
    );
  };

  const allFieldsFilled = () => {
    // Check if all dynamic fields are filled
    const dynamicFieldsFilled = dynamicFields.every(
      (field) => field.key && field.value
    );
    const dependenciesFilled = !dependenciesErrors.some((error) => error);
    return dynamicFieldsFilled && dependenciesFilled;
  };

  const handleAddField = (e: React.FormEvent) => {
    setDynamicFields([...dynamicFields, { key: "", value: "" }]);
    e.preventDefault();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // verify all fields are filled
    const dynamicFieldErrors = dynamicFields.map(
      (field) => !field.key || !field.value
    );
    setFieldErrors(dynamicFieldErrors);

    // Verify dependencies have values
    const newDependenciesErrors = dependencies.map(
      (dep) => !dependencyValues[dep]
    );
    setDependenciesErrors(newDependenciesErrors);

    // Check if there are errors in dynamic fields or dependencies
    const hasErrors =
      dynamicFieldErrors.some((error) => error) ||
      newDependenciesErrors.some((error) => error);

    if (hasErrors) {
      return; // Stop the form submission if there are errors
    }

    if (!allFieldsFilled()) {
      return;
    }

    // build the final payload
    const buildNestedObject = (
      acc: Record<string, any>,
      key: string,
      value: string
    ) => {
      const keys = key.split(".");
      let current = acc;

      for (let i = 0; i < keys.length - 1; i++) {
        const part = keys[i];
        current[part] = current[part] || {};
        current = current[part];
      }

      current[keys[keys.length - 1]] = value;
      return acc;
    };

    // Construct payload with a flexible structure
    const payload: Record<string, any> = dynamicFields.reduce((acc, field) => {
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

    onClose();
    onSubmit(payload);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Build Alert Payload">
      <form onSubmit={handleSubmit}>
        {Array.isArray(staticFields) && staticFields.length > 0 && (
          <>
            <Text className="mb-2">Fields Defined As Workflow Filters</Text>
            {staticFields.map((field, index) => (
              <div key={field.key} className="flex gap-2 mb-2">
                <TextInput placeholder="Key" value={field.key} disabled />
                <TextInput placeholder="Value" value={field.value} disabled />
              </div>
            ))}
          </>
        )}

        <Text className="mb-2">
          These fields are needed for the workflow to run
        </Text>
        {Array.isArray(dependencies) &&
          dependencies.map((dependencyName, index) => (
            <div key={dependencyName} className="flex gap-2 mb-2">
              <TextInput
                placeholder={dependencyName}
                value={dependencyName}
                disabled
              />
              <TextInput
                placeholder="value"
                value={dependencyValues[dependencyName] || ""}
                onChange={(e) =>
                  handleDependencyChange(dependencyName, e.target.value)
                }
                error={dependenciesErrors[index]}
              />
            </div>
          ))}

        {dynamicFields.map((field, index) => (
          <div
            key={index}
            className={`flex items-center gap-2 mb-2 ${
              fieldErrors[index] ? "border-2 border-red-500 p-2" : ""
            }`}
          >
            <TextInput
              placeholder="Key"
              value={field.key}
              onChange={(e) => handleFieldChange(index, "key", e.target.value)}
            />
            <TextInput
              placeholder="Value"
              value={field.value}
              onChange={(e) =>
                handleFieldChange(index, "value", e.target.value)
              }
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

        <div className="mt-8 flex justify-end gap-2">
          <Button
            onClick={onClose}
            variant="secondary"
            className="border border-orange-500 text-orange-500"
          >
            Cancel
          </Button>
          <Button color="orange" type="submit">
            Run workflow
          </Button>
        </div>
      </form>
    </Modal>
  );
}
