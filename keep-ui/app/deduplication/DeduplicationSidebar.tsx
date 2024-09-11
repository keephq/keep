import React, { Fragment, useEffect, useState } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { useForm, Controller, SubmitHandler } from "react-hook-form";
import { Text, Button, TextInput, Callout, Badge, Select, SelectItem, MultiSelect, MultiSelectItem, Switch } from "@tremor/react";
import { IoMdClose } from "react-icons/io";
import { DeduplicationRule } from "app/deduplication/models";
import { useProviders } from "utils/hooks/useProviders";
import { useDeduplicationFields } from "utils/hooks/useDeduplicationRules";

interface DeduplicationSidebarProps {
  isOpen: boolean;
  toggle: VoidFunction;
  defaultValue?: Partial<DeduplicationRule>;
  onSubmit: (data: Partial<DeduplicationRule>) => Promise<void>;
}

const DeduplicationSidebar: React.FC<DeduplicationSidebarProps> = ({
  isOpen,
  toggle,
  defaultValue,
  onSubmit,
}) => {
  const { control, handleSubmit, setValue, reset, setError, watch, formState: { errors }, clearErrors } = useForm<Partial<DeduplicationRule>>({
    defaultValues: defaultValue || {
      name: "",
      description: "",
      provider_type: "",
      fingerprint_fields: [],
      full_deduplication: false,
      ignore_fields: [],
    },
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const { data: providers = { installed_providers: [], linked_providers: [] } } = useProviders();
  const { data: deduplicationFields = [] } = useDeduplicationFields();

  const alertProviders = [...providers.installed_providers, ...providers.linked_providers].filter(
    provider => provider.tags?.includes("alert")
  );

  const fullDeduplication = watch("full_deduplication");

  useEffect(() => {
    if (isOpen && defaultValue) {
      reset(defaultValue);
    } else if (isOpen) {
      reset({
        name: "",
        description: "",
        provider_type: "",
        fingerprint_fields: [],
        full_deduplication: false,
        ignore_fields: [],
      });
    }
  }, [isOpen, defaultValue, reset]);

  const handleToggle = () => {
    if (isOpen) {
      clearErrors();
    }
    toggle();
  };

  const onFormSubmit: SubmitHandler<Partial<DeduplicationRule>> = async (data) => {
    setIsSubmitting(true);
    clearErrors();
    try {
      await onSubmit(data);
      handleToggle();
    } catch (error) {
      setError("root.serverError", { type: "manual", message: "Failed to save deduplication rule" });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog onClose={handleToggle}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/30 z-20" aria-hidden="true" />
        </Transition.Child>
        <Transition.Child
          as={Fragment}
          enter="transition ease-in-out duration-300 transform"
          enterFrom="translate-x-full"
          enterTo="translate-x-0"
          leave="transition ease-in-out duration-300 transform"
          leaveFrom="translate-x-0"
          leaveTo="translate-x-full"
        >
          <Dialog.Panel className="fixed right-0 inset-y-0 w-3/4 bg-white z-30 p-6 overflow-auto flex flex-col">
            <div className="flex justify-between mb-4">
              <Dialog.Title className="text-3xl font-bold" as={Text}>
                {defaultValue ? "Edit Deduplication Rule" : "Add Deduplication Rule"}
                <Badge className="ml-4" color="orange">Beta</Badge>
              </Dialog.Title>
              <Button onClick={toggle} variant="light">
                <IoMdClose className="h-6 w-6 text-gray-500" />
              </Button>
            </div>
            <form onSubmit={handleSubmit(onFormSubmit)} className="mt-4 flex flex-col h-full">
              <div className="flex-grow">
                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700">
                    Rule Name
                  </label>
                  <Controller
                    name="name"
                    control={control}
                    rules={{ required: "Rule name is required" }}
                    render={({ field }) => (
                      <TextInput
                        {...field}
                        error={!!errors.name}
                        errorMessage={errors.name?.message}
                      />
                    )}
                  />
                </div>
                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700">
                    Description
                  </label>
                  <Controller
                    name="description"
                    control={control}
                    rules={{ required: "Description is required" }}
                    render={({ field }) => (
                      <TextInput
                        {...field}
                        error={!!errors.description}
                        errorMessage={errors.description?.message}
                      />
                    )}
                  />
                </div>
                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700">
                    Provider Type
                  </label>
                  <Controller
                    name="provider_type"
                    control={control}
                    rules={{ required: "Provider type is required" }}
                    render={({ field }) => (
                      <Select
                        {...field}
                        placeholder="Select provider type"
                        error={!!errors.provider_type}
                        errorMessage={errors.provider_type?.message}
                      >
                        {alertProviders.map((provider) => (
                          <SelectItem key={provider.id} value={provider.type}>
                            {provider.type} {provider.name || provider.id}
                          </SelectItem>
                        ))}
                      </Select>
                    )}
                  />
                </div>
                <div className="mt-4">
                  <label className="block text-sm font-medium text-gray-700">
                    Fingerprint Fields
                  </label>
                  <Controller
                    name="fingerprint_fields"
                    control={control}
                    rules={{ required: "At least one fingerprint field is required" }}
                    render={({ field }) => (
                      <MultiSelect
                        {...field}
                        placeholder="Select fingerprint fields"
                        error={!!errors.fingerprint_fields}
                        errorMessage={errors.fingerprint_fields?.message}
                      >
                        {deduplicationFields.map((fieldName) => (
                          <MultiSelectItem key={fieldName} value={fieldName}>
                            {fieldName}
                          </MultiSelectItem>
                        ))}
                      </MultiSelect>
                    )}
                  />
                </div>
                <div className="mt-4">
                  <label className="flex items-center space-x-2">
                    <Controller
                      name="full_deduplication"
                      control={control}
                      render={({ field }) => (
                        <Switch
                          checked={field.value}
                          onChange={field.onChange}
                        />
                      )}
                    />
                    <span className="text-sm font-medium text-gray-700">Full Deduplication</span>
                  </label>
                </div>
                {fullDeduplication && (
                  <div className="mt-4">
                    <label className="block text-sm font-medium text-gray-700">
                      Ignore Fields
                    </label>
                    <Controller
                      name="ignore_fields"
                      control={control}
                      render={({ field }) => (
                        <MultiSelect
                          {...field}
                          placeholder="Select ignore fields"
                          error={!!errors.ignore_fields}
                          errorMessage={errors.ignore_fields?.message}
                        >
                          {deduplicationFields.map((fieldName) => (
                            <MultiSelectItem key={fieldName} value={fieldName}>
                              {fieldName}
                            </MultiSelectItem>
                          ))}
                        </MultiSelect>
                      )}
                    />
                  </div>
                )}
                {errors.root?.serverError && (
                  <Callout className="mt-4" title="Error while saving rule" color="rose">
                    {errors.root.serverError.message}
                  </Callout>
                )}
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <Button
                  color="orange"
                  variant="secondary"
                  onClick={handleToggle}
                  className="border border-orange-500 text-orange-500"
                >
                  Cancel
                </Button>
                <Button
                  color="orange"
                  type="submit"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Saving..." : "Save Rule"}
                </Button>
              </div>
            </form>
          </Dialog.Panel>
        </Transition.Child>
      </Dialog>
    </Transition>
  );
};

export default DeduplicationSidebar;
