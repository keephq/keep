import { useMemo, useState } from "react";
import { Button, Text } from "@tremor/react";
import { TextInput } from "@/components/ui";
import { PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import { JsonCard } from "@/shared/ui/JsonCard";
import { buildNestedObject } from "@/shared/lib/buildNestedObject";
import {
  AlertWorkflowRunPayload,
  IncidentWorkflowRunPayload,
} from "@/features/workflows/manual-run-workflow/model/types";

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
  value: string | number | boolean | string[] | number[] | boolean[];
}

type Payload = Record<string, any>;

interface WorkflowAlertDependenciesFormProps {
  type: "alert";
  dependencies: string[];
  staticFields: Field[];
  submitLabel?: string;
  onCancel: () => void;
  onSubmit: (payload: AlertWorkflowRunPayload) => void;
}

type WorkflowIncidentDependenciesFormProps = {
  type: "incident";
  dependencies: string[];
  staticFields: Field[];
  submitLabel?: string;
  onCancel: () => void;
  onSubmit: (payload: IncidentWorkflowRunPayload) => void;
};

type WorkflowDependenciesFormProps =
  | WorkflowAlertDependenciesFormProps
  | WorkflowIncidentDependenciesFormProps;

export function WorkflowAlertIncidentDependenciesForm({
  type,
  dependencies,
  staticFields,
  onCancel,
  onSubmit,
  submitLabel = "Continue",
}: WorkflowDependenciesFormProps) {
  const [dynamicFields, setDynamicFields] = useState<Field[]>([]);
  const [fieldErrors, setFieldErrors] = useState<
    Record<number, { key: boolean; value: boolean }>
  >({});
  const [dependenciesErrors, setDependenciesErrors] = useState<
    Record<number, boolean>
  >({});
  const [dependencyValues, setDependencyValues] = useState<
    Record<string, string>
  >({});

  const validateDynamicFields = (newDynamicFields: Field[]) => {
    // verify all fields are filled
    const errors: Record<number, { key: boolean; value: boolean }> = {};
    newDynamicFields.forEach((field, index) => {
      if (!field.key || !field.value) {
        errors[index] = {
          key: !field.key,
          value: !field.value,
        };
      }
    });
    return errors;
  };

  const validateDependencies = (
    dependencies: string[],
    newDependencyValues: Record<string, string>
  ) => {
    // Verify dependencies have values
    const errors: Record<number, boolean> = {};
    dependencies.forEach((dep, index) => {
      if (!newDependencyValues[dep]) {
        errors[index] = true;
      }
    });
    return errors;
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

    // Re-validate all fields
    setFieldErrors(validateDynamicFields(newDynamicFields));
  };

  const handleDependencyChange = (dependencyName: string, newValue: string) => {
    const newDependencyValues = {
      ...dependencyValues,
      [dependencyName]: newValue,
    };
    setDependencyValues(newDependencyValues);

    // Re-validate dependencies
    setDependenciesErrors(
      validateDependencies(dependencies, newDependencyValues)
    );
  };

  const handleDeleteField = (index: number) => {
    const newDynamicFields = dynamicFields.filter((_, i) => i !== index);
    setDynamicFields(newDynamicFields);

    // Re-validate remaining fields
    const newErrors = validateDynamicFields(newDynamicFields);
    setFieldErrors(newErrors);
  };

  const handleAddField = (e: React.FormEvent) => {
    e.preventDefault();
    setDynamicFields([...dynamicFields, { key: "", value: "" }]);
    // it's intentional to validate previous fields, since new fields are not touched yet and we don't want to yell at user for no reason
    setFieldErrors(validateDynamicFields(dynamicFields));
  };

  const payload = useMemo(() => {
    return getAlertPayload(dynamicFields, dependencyValues, staticFields);
  }, [dynamicFields, dependencyValues, staticFields]);

  const isValid = useMemo(() => {
    const fieldErrorsExist = Object.keys(fieldErrors).length > 0;
    const depErrorsExist = Object.keys(dependenciesErrors).length > 0;
    return !fieldErrorsExist && !depErrorsExist;
  }, [fieldErrors, dependenciesErrors]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const dynamicFieldErrors = validateDynamicFields(dynamicFields);
    const dependencyValidationErrors = validateDependencies(
      dependencies,
      dependencyValues
    );
    setFieldErrors(dynamicFieldErrors);
    setDependenciesErrors(dependencyValidationErrors);

    const fieldErrorsExist = Object.keys(dynamicFieldErrors).length > 0;
    const depErrorsExist = Object.keys(dependencyValidationErrors).length > 0;

    if (fieldErrorsExist || depErrorsExist) {
      return;
    }

    const payload = getAlertPayload(
      dynamicFields,
      dependencyValues,
      staticFields
    );

    if (type === "alert") {
      onSubmit({ type, body: payload } as AlertWorkflowRunPayload);
    } else if (type === "incident") {
      onSubmit({ type, body: payload } as IncidentWorkflowRunPayload);
    } else {
      throw new Error("Invalid type");
    }
  };

  const keyClassName = "w-2/6 font-mono";
  const valueClassName = "flex-1 font-mono";

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={handleSubmit}
      data-testid={`wf-${type}-dependencies-form`}
    >
      <header>
        <Text className="font-bold">
          Build {type === "alert" ? "Alert" : "Incident"} payload required to
          run the workflow
        </Text>
      </header>
      <div className="flex flex-col md:flex-row gap-4">
        <div className="flex-1">
          {Array.isArray(staticFields) && staticFields.length > 0 && (
            <section>
              <Text className="mb-2">
                {type === "alert"
                  ? "Fields defined in alert trigger filters"
                  : "Mocked default values for incident fields"}
              </Text>
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
                    value={
                      typeof field.value === "string"
                        ? field.value
                        : JSON.stringify(field.value)
                    }
                    className={valueClassName}
                    disabled
                  />
                </div>
              ))}
            </section>
          )}

          <section>
            <Text className="mb-2">
              {type === "alert" ? "Alert" : "Incident"} fields used in the
              workflow
            </Text>
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
                    name={dependencyName}
                    placeholder="value"
                    value={
                      typeof dependencyValues[dependencyName] === "string"
                        ? dependencyValues[dependencyName]
                        : JSON.stringify(dependencyValues[dependencyName])
                    }
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
                  name={"key-" + field.key}
                  value={field.key}
                  className={keyClassName}
                  onChange={(e) =>
                    handleFieldChange(index, "key", e.target.value)
                  }
                  error={fieldErrors[index]?.key}
                />
                <TextInput
                  name={field.key}
                  placeholder="value"
                  value={
                    typeof field.value === "string"
                      ? field.value
                      : JSON.stringify(field.value)
                  }
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
        </div>
        <div className="flex-1">
          {payload && (
            <JsonCard
              title={`${type}Payload (readonly)`}
              json={payload}
              maxHeight={400}
            />
          )}
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" color="orange" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="submit"
          variant="primary"
          color="orange"
          disabled={!isValid}
          data-testid={`wf-${type}-dependencies-form-submit`}
        >
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
