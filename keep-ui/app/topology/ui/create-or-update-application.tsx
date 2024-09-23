import { Button } from "@tremor/react";
import { TextInput, Textarea, AutocompleteInput } from "@/components/ui";
import { useCallback, useState } from "react";
import { useTopology } from "utils/hooks/useTopology";
import { Application } from "../models";
import { Icon } from "@tremor/react";
import { MagnifyingGlassIcon, XMarkIcon } from "@heroicons/react/24/solid";

type FormErrors = {
  name?: string;
  services?: string;
};

type CreateApplicationFormProps = {
  action: "create";
  application: Pick<Application, "services">;
  onSubmit: (application: Omit<Application, "id">) => void;
  onCancel: () => void;
};

type UpdateApplicationFormProps = {
  action: "edit";
  application: Application;
  onSubmit: (application: Application) => void;
  onCancel: () => void;
};

type CreatOrUpdateApplicationFormProps =
  | CreateApplicationFormProps
  | UpdateApplicationFormProps;

export function CreateOrUpdateApplicationForm({
  action,
  application,
  onSubmit,
  onCancel,
}: CreatOrUpdateApplicationFormProps) {
  const { topologyData } = useTopology();
  const [applicationName, setApplicationName] = useState(
    action === "edit" ? application.name : ""
  );
  const [applicationDescription, setApplicationDescription] = useState(
    action === "edit" ? application.description : ""
  );
  const applicationId = action === "edit" ? application.id : undefined;

  const [selectedServices, setSelectedServices] = useState<
    { id: string; name: string }[]
  >(application?.services || []);
  const [errors, setErrors] = useState<FormErrors>({});

  const validateForm = (formValues: Omit<Application, "id">): FormErrors => {
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
      if (action === "edit") {
        onSubmit({
          ...formValues,
          id: applicationId!,
        });
      } else {
        onSubmit(formValues);
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
                  key={service.id}
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
          <AutocompleteInput<string>
            className="hover:bg-gray-100 border-0 shadow-none !rounded-t-none [&>input]:rounded-t-none"
            icon={MagnifyingGlassIcon}
            options={
              topologyData
                ?.map((service) => ({
                  label: service.display_name,
                  value: service.service.toString(),
                }))
                .filter(
                  (service) =>
                    !selectedServices.some((s) => s.id === service.value)
                ) || []
            }
            onSelect={(option, clearInput) => {
              setSelectedServices([
                ...selectedServices,
                { id: option.value, name: option.label },
              ]);
              clearInput();
            }}
            placeholder="Search services by name or id"
          />
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <Button color="orange" size="xs" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button color="orange" size="xs" type="submit">
          {action === "create" ? "Create" : "Update"}
        </Button>
      </div>
    </form>
  );
}
