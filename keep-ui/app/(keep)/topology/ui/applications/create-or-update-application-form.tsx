import { Callout } from "@tremor/react";
import { TextInput, Textarea, Button } from "@/components/ui";
import { useCallback, useState } from "react";
import {
  TopologyApplication,
  TopologyServiceMinimal,
} from "@/app/(keep)/topology/model";
import { Icon } from "@tremor/react";
import { XMarkIcon } from "@heroicons/react/24/solid";
import { TopologySearchAutocomplete } from "../TopologySearchAutocomplete";

type FormErrors = {
  name?: string;
  services?: string;
};

type BaseProps = {
  onCancel: () => void;
};

type CreateProps = BaseProps & {
  action: "create";
  application?: Partial<TopologyApplication>;
  onSubmit: (application: Omit<TopologyApplication, "id">) => Promise<void>;
  onDelete?: undefined;
};

type UpdateProps = BaseProps & {
  action: "edit";
  application: TopologyApplication;
  onSubmit: (application: TopologyApplication) => Promise<void>;
  onDelete: () => void;
};

type CreatOrUpdateApplicationFormProps = CreateProps | UpdateProps;

export function CreateOrUpdateApplicationForm({
  action,
  application,
  onSubmit,
  onCancel,
  onDelete,
}: CreatOrUpdateApplicationFormProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [applicationName, setApplicationName] = useState(
    action === "edit" ? application.name : ""
  );
  const [applicationDescription, setApplicationDescription] = useState(
    action === "edit" ? application.description : ""
  );
  const applicationId = action === "edit" ? application.id : undefined;

  const [selectedServices, setSelectedServices] = useState<
    TopologyServiceMinimal[]
  >(application?.services || []);
  const [errors, setErrors] = useState<FormErrors>({});

  const validateForm = (
    formValues: Omit<TopologyApplication, "id">
  ): FormErrors => {
    const newErrors: FormErrors = {};
    if (!formValues.name.trim()) {
      newErrors.name = "Enter the application name";
    }
    if (formValues.services.length === 0) {
      newErrors.services = "Select at least one service";
    }
    return newErrors;
  };

  const handleSubmit = useCallback(
    (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const formValues = {
        name: applicationName,
        description: applicationDescription,
        services: selectedServices,
      };
      const validationErrors = validateForm(formValues);
      if (Object.keys(validationErrors).length > 0) {
        setErrors(validationErrors);
        return;
      }
      setErrors({});
      setIsLoading(true);
      if (action === "create") {
        onSubmit(formValues)
          .catch((error) => {
            setError(error);
          })
          .finally(() => {
            setIsLoading(false);
          });
      } else if (action === "edit") {
        onSubmit({ ...formValues, id: applicationId! })
          .catch((error) => {
            setError(error);
          })
          .finally(() => {
            setIsLoading(false);
          });
      }
    },
    [
      action,
      applicationName,
      applicationDescription,
      selectedServices,
      applicationId,
      onSubmit,
    ]
  );

  return (
    <form
      className="flex flex-col gap-4 text-tremor-content-emphasis"
      onSubmit={handleSubmit}
    >
      <p className="">Group services into an application</p>
      <div>
        <div className="mb-1">
          <span className="font-bold">Application name</span>
          {errors.name && (
            <p className="text-red-500 text-sm mt-1">{errors.name}</p>
          )}
        </div>
        <TextInput
          placeholder="Application name"
          value={applicationName}
          onChange={(e) => setApplicationName(e.target.value)}
          required={true}
        />
      </div>
      <div>
        <div className="mb-1">
          <span className="font-bold">Description (optional)</span>
        </div>
        <Textarea
          placeholder="Description (optional)"
          value={applicationDescription}
          onChange={(e) => setApplicationDescription(e.target.value)}
        />
      </div>
      <div className="flex flex-col gap-2">
        <div>
          <span className="font-bold">Selected services</span>
          {errors.services && (
            <p className="text-red-500 text-sm mt-1">{errors.services}</p>
          )}
        </div>
        <div className="flex flex-col border border-gray-200 rounded-tremor-default">
          {selectedServices.length > 0 && (
            <ul className="flex flex-wrap gap-2 max-h-60 overflow-auto p-2">
              {selectedServices.map((service) => (
                <li
                  key={service.service}
                  className="text-sm inline-flex justify-between bg-gray-100 rounded-md"
                >
                  <span className="text-gray-800 p-2 pr-0">{service.name}</span>
                  <Button
                    variant="light"
                    className="group"
                    onClick={() => {
                      setSelectedServices(
                        selectedServices.filter((s) => s !== service)
                      );
                    }}
                  >
                    <Icon
                      icon={XMarkIcon}
                      className="text-gray-400 group-hover:text-gray-500"
                    />
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <TopologySearchAutocomplete
            placeholder="Search services by name or id"
            includeApplications={false}
            excludeServiceIds={selectedServices.map((s) => s.service)}
            onSelect={({ value }: { value: TopologyServiceMinimal }) => {
              setSelectedServices([...selectedServices, value]);
            }}
          />
        </div>
      </div>
      {error && (
        <Callout title="Error" color="red">
          {error.message}
        </Callout>
      )}
      <div className="flex justify-between gap-2">
        {onDelete && (
          <Button
            color="red"
            size="xs"
            variant="destructive"
            onClick={onDelete}
          >
            Delete
          </Button>
        )}
        <div className="flex flex-1 justify-end gap-2">
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            onClick={onCancel}
          >
            Cancel
          </Button>
          <Button
            color="orange"
            size="xs"
            variant="primary"
            type="submit"
            loading={isLoading}
          >
            {action === "create" ? "Create" : "Update"}
          </Button>
        </div>
      </div>
    </form>
  );
}
