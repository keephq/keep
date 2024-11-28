import { useEffect, useState, useMemo } from "react";
import { Dialog } from "@headlessui/react";
import { useForm, Controller, SubmitHandler } from "react-hook-form";
import {
  Text,
  Button,
  TextInput,
  Callout,
  Badge,
  Switch,
  Icon,
  Title,
  Card,
} from "@tremor/react";
import { IoMdClose } from "react-icons/io";
import { DeduplicationRule } from "@/app/(keep)/deduplication/models";
import { useDeduplicationFields } from "utils/hooks/useDeduplicationRules";
import { GroupBase } from "react-select";
import Select from "@/components/ui/Select";
import MultiSelect from "@/components/ui/MultiSelect";
import {
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from "@heroicons/react/24/outline";
import { KeyedMutator } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { Providers } from "@/app/(keep)/providers/providers";
import SidePanel from "@/components/SidePanel";

interface ProviderOption {
  value: string;
  label: string;
  logoUrl: string;
}

interface DeduplicationSidebarProps {
  isOpen: boolean;
  toggle: VoidFunction;
  selectedDeduplicationRule: DeduplicationRule | null;
  onSubmit: (data: Partial<DeduplicationRule>) => Promise<void>;
  mutateDeduplicationRules: KeyedMutator<DeduplicationRule[]>;
  providers: { installed_providers: Providers; linked_providers: Providers };
}

const DeduplicationSidebar: React.FC<DeduplicationSidebarProps> = ({
  isOpen,
  toggle,
  selectedDeduplicationRule,
  onSubmit,
  mutateDeduplicationRules,
  providers,
}) => {
  const {
    control,
    handleSubmit,
    setValue,
    reset,
    setError,
    watch,
    formState: { errors },
    clearErrors,
  } = useForm<Partial<DeduplicationRule>>({
    defaultValues: selectedDeduplicationRule || {
      name: "",
      description: "",
      provider_type: "",
      provider_id: "",
      fingerprint_fields: [],
      full_deduplication: false,
      ignore_fields: [],
    },
  });

  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data: deduplicationFields = {} } = useDeduplicationFields();
  const api = useApi();

  const alertProviders = useMemo(
    () =>
      [
        { id: null, type: "keep", details: { name: "Keep" }, tags: ["alert"] },
        ...providers.installed_providers,
        ...providers.linked_providers,
      ].filter((provider) => provider.tags?.includes("alert")),
    [providers]
  );
  const fullDeduplication = watch("full_deduplication");
  const selectedProviderType = watch("provider_type");
  const selectedProviderId = watch("provider_id");
  const fingerprintFields = watch("fingerprint_fields");
  const ignoreFields = watch("ignore_fields");

  const availableFields = useMemo(() => {
    const defaultFields = [
      "source",
      "service",
      "description",
      "fingerprint",
      "name",
      "lastReceived",
    ];
    if (selectedProviderType) {
      const key = `${selectedProviderType}_${selectedProviderId || "null"}`;
      const providerFields = deduplicationFields[key] || [];
      return [
        ...new Set([
          ...defaultFields,
          ...providerFields,
          ...(fingerprintFields ?? []),
          ...(ignoreFields ?? []),
        ]),
      ];
    }
    return [...new Set([...defaultFields, ...(fingerprintFields ?? [])])];
  }, [
    selectedProviderType,
    selectedProviderId,
    deduplicationFields,
    fingerprintFields,
    ignoreFields,
  ]);

  useEffect(() => {
    if (isOpen && selectedDeduplicationRule) {
      reset(selectedDeduplicationRule);
    } else if (isOpen) {
      reset({
        name: "",
        description: "",
        provider_type: "",
        provider_id: "",
        fingerprint_fields: [],
        full_deduplication: false,
        ignore_fields: [],
      });
    }
  }, [isOpen, selectedDeduplicationRule, reset]);

  const handleToggle = () => {
    if (isOpen) {
      clearErrors();
    }
    toggle();
  };

  const onFormSubmit: SubmitHandler<Partial<DeduplicationRule>> = async (
    data
  ) => {
    setIsSubmitting(true);
    clearErrors();
    try {
      let url = "/deduplications";

      if (selectedDeduplicationRule && selectedDeduplicationRule.id) {
        url += `/${selectedDeduplicationRule.id}`;
      }

      const method =
        !selectedDeduplicationRule || !selectedDeduplicationRule.id
          ? "POST"
          : "PUT";

      const response =
        method === "POST"
          ? await api.post(url, data)
          : await api.put(url, data);

      console.log("Deduplication rule saved:", data);
      reset();
      handleToggle();
      await mutateDeduplicationRules();
    } catch (error) {
      if (error instanceof KeepApiError) {
        setError("root.serverError", {
          type: "manual",
          message: error.message || "Failed to save deduplication rule",
        });
      } else {
        setError("root.serverError", {
          type: "manual",
          message: "An unexpected error occurred",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SidePanel isOpen={isOpen} onClose={handleToggle}>
      <div className="flex justify-between mb-4">
        <div>
          <Dialog.Title className="text-3xl font-bold" as={Title}>
            {selectedDeduplicationRule
              ? "Edit Deduplication Rule"
              : "Add Deduplication Rule"}
            <Badge className="ml-4" color="orange">
              Beta
            </Badge>
            {selectedDeduplicationRule?.default && (
              <Badge className="ml-2" color="orange">
                Default Rule
              </Badge>
            )}
          </Dialog.Title>
        </div>
        <div>
          <Button onClick={toggle} variant="light">
            <IoMdClose className="h-6 w-6 text-gray-500" />
          </Button>
        </div>
      </div>

      {selectedDeduplicationRule?.default && (
        <div className="flex flex-col">
          <Callout
            className="mb-4 py-8"
            title="Editing a Default Rule"
            icon={ExclamationTriangleIcon}
            color="orange"
          >
            <Text>
              Editing a default deduplication rule requires advanced knowledge.
              Default rules are carefully designed to provide optimal
              deduplication for specific alert types. Modifying these rules may
              impact the efficiency of your alert processing. If you&apos;re
              unsure about making changes, we recommend creating a new custom
              rule instead of modifying the default one.
            </Text>
            <br></br>
            <a
              href="https://docs.keephq.dev/overview/deduplication"
              target="_blank"
              className="text-orange-600 hover:underline mt-4"
            >
              Learn more about deduplication rules
            </a>
          </Callout>
        </div>
      )}

      <form
        onSubmit={handleSubmit(onFormSubmit)}
        className="mt-4 flex flex-col h-full"
      >
        <div className="flex-grow space-y-4">
          <Card>
            <div className="space-y-4">
              <div>
                <Text className="block text-sm font-medium text-gray-700 mb-2">
                  Rule name
                </Text>
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
              <div>
                <Text className="block text-sm font-medium text-gray-700 mb-2">
                  Description
                </Text>
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
              <div>
                <span className="text-sm font-medium text-gray-700 flex items-center mb-2">
                  Provider
                  <span className="ml-1 relative inline-flex items-center">
                    <span className="group relative flex items-center">
                      <Icon
                        icon={InformationCircleIcon}
                        className="w-[1em] h-[1em] text-gray-500"
                      />
                      <span className="absolute bottom-full left-full p-2 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity duration-300 w-80 text-center pointer-events-none group-hover:pointer-events-auto">
                        Select the provider for which this deduplication rule
                        will apply. This determines the source of alerts that
                        will be processed by this rule.
                      </span>
                    </span>
                  </span>
                </span>
                <Controller
                  name="provider_type"
                  control={control}
                  rules={{ required: "Provider is required" }}
                  render={({ field }) => (
                    <Select<ProviderOption, false, GroupBase<ProviderOption>>
                      {...field}
                      isDisabled={!!selectedDeduplicationRule?.default}
                      options={alertProviders.map((provider) => ({
                        value: `${provider.type}_${provider.id}`,
                        label: provider.details?.name || provider.id || "main",
                        logoUrl: `/icons/${provider.type}-icon.png`,
                      }))}
                      placeholder="Select provider"
                      onChange={(selectedOption) => {
                        if (selectedOption) {
                          const [providerType, providerId] =
                            selectedOption.value.split("_");
                          setValue("provider_type", providerType);
                          setValue("provider_id", providerId as any);
                        }
                      }}
                      value={
                        alertProviders.find(
                          (provider) =>
                            `${provider.type}_${provider.id}` ===
                            `${selectedProviderType}_${selectedProviderId}`
                        )
                          ? ({
                              value: `${selectedProviderType}_${selectedProviderId}`,
                              label:
                                alertProviders.find(
                                  (provider) =>
                                    `${provider.type}_${provider.id}` ===
                                    `${selectedProviderType}_${selectedProviderId}`
                                )?.details?.name ||
                                (selectedProviderId !== "null" &&
                                selectedProviderId !== null
                                  ? selectedProviderId
                                  : "main"),
                              logoUrl: `/icons/${selectedProviderType}-icon.png`,
                            } as ProviderOption)
                          : null
                      }
                    />
                  )}
                />
                {errors.provider_type && (
                  <p className="mt-1 text-sm text-red-600">
                    {errors.provider_type.message}
                  </p>
                )}
              </div>
              <div>
                <span className="text-sm font-medium text-gray-700 flex items-center mb-2">
                  Fields to use for fingerprint
                  <span className="ml-1 relative inline-flex items-center">
                    <span className="group relative flex items-center">
                      <Icon
                        icon={InformationCircleIcon}
                        className="w-[1em] h-[1em] text-gray-500"
                      />
                      <span className="absolute bottom-full left-1/2 transform -translate-x-1/2 p-2 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity duration-300 w-80 text-center pointer-events-none group-hover:pointer-events-auto">
                        Fingerprint fields are used to identify and group
                        similar alerts. Choose fields that uniquely identify an
                        alert type, such as &apos;service&apos;,
                        &apos;error_type&apos;, or
                        &apos;affected_component&apos;.
                      </span>
                    </span>
                  </span>
                </span>
                <Controller
                  name="fingerprint_fields"
                  control={control}
                  rules={{
                    required: "At least one fingerprint field is required",
                  }}
                  render={({ field }) => (
                    <MultiSelect
                      {...field}
                      options={availableFields.map((fieldName) => ({
                        value: fieldName,
                        label: fieldName,
                      }))}
                      placeholder="Select fingerprint fields"
                      value={field.value?.map((value: string) => ({
                        value,
                        label: value,
                      }))}
                      onChange={(selectedOptions) => {
                        field.onChange(
                          selectedOptions.map(
                            (option: { value: string }) => option.value
                          )
                        );
                      }}
                      noOptionsMessage={() =>
                        selectedProviderType
                          ? "No options"
                          : "Please choose provider to see available fields"
                      }
                    />
                  )}
                />
                {errors.fingerprint_fields && (
                  <p className="mt-1 text-sm text-red-600">
                    {errors.fingerprint_fields.message}
                  </p>
                )}
              </div>
              <div>
                <Text className="flex items-center space-x-2">
                  <Controller
                    name="full_deduplication"
                    control={control}
                    render={({ field }) => (
                      <Switch checked={field.value} onChange={field.onChange} />
                    )}
                  />
                  <span className="text-sm font-medium text-gray-700 flex items-center">
                    Full deduplication
                    <span className="ml-1 relative inline-flex items-center">
                      <span className="group relative flex items-center">
                        <Icon
                          icon={InformationCircleIcon}
                          className="w-[1em] h-[1em] text-gray-500"
                        />
                        <span className="absolute bottom-full left-1/2 transform -translate-x-1/2 p-2 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity duration-300 w-80 text-center pointer-events-none group-hover:pointer-events-auto">
                          1. Full deduplication: Keep will discard events if
                          they are the same (excluding the &apos;Ignore
                          Fields&apos;).
                          <br />
                          2. Partial deduplication (default): Uses specified
                          fields to correlate alerts. E.g., two alerts with same
                          &apos;service&apos; and &apos;env&apos; fields will be
                          deduped into one alert.
                        </span>
                      </span>
                    </span>
                  </span>
                </Text>
              </div>

              {fullDeduplication && (
                <div>
                  <Text className="block text-sm font-medium text-gray-700 mb-2">
                    Ignore fields
                  </Text>
                  <Controller
                    name="ignore_fields"
                    control={control}
                    render={({ field }) => (
                      <MultiSelect
                        {...field}
                        options={availableFields.map((fieldName) => ({
                          value: fieldName,
                          label: fieldName,
                        }))}
                        placeholder="Select ignore fields"
                        value={field.value?.map((value: string) => ({
                          value,
                          label: value,
                        }))}
                        onChange={(selectedOptions) => {
                          field.onChange(
                            selectedOptions.map(
                              (option: { value: string }) => option.value
                            )
                          );
                        }}
                      />
                    )}
                  />
                  {errors.ignore_fields && (
                    <p className="mt-1 text-sm text-red-600">
                      {errors.ignore_fields.message}
                    </p>
                  )}
                </div>
              )}
            </div>
          </Card>
          {errors.root?.serverError && (
            <Callout
              className="mt-4"
              title="Error while saving rule"
              color="rose"
            >
              {errors.root.serverError.message}
            </Callout>
          )}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button
            color="orange"
            variant="secondary"
            onClick={handleToggle}
            type="button"
            className="border border-orange-500 text-orange-500"
          >
            Cancel
          </Button>
          <Button color="orange" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving..." : "Save Rule"}
          </Button>
        </div>
      </form>
    </SidePanel>
  );
};

export default DeduplicationSidebar;
