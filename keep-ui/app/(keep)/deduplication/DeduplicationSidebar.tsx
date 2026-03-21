import { useI18n } from "@/i18n/hooks/useI18n";
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
import { Select } from "@/shared/ui";
import {
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from "@heroicons/react/24/outline";
import { KeyedMutator } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { Providers } from "@/shared/api/providers";
import SidePanel from "@/components/SidePanel";
import { useConfig } from "@/utils/hooks/useConfig";

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
  const { t } = useI18n();
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

  const { data: config } = useConfig();

  const { data: deduplicationFields = {} } = useDeduplicationFields();
  const api = useApi();

  const alertProviders = useMemo(
    () =>
      [
        { id: null, type: "keep", details: { name: t("rules.deduplication.form.keepProvider") }, tags: ["alert"] },
        ...providers.installed_providers,
        ...providers.linked_providers,
      ].filter((provider) => provider.tags?.includes("alert")),
    [providers, t]
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
          message: error.message || t("rules.deduplication.messages.saveFailed"),
        });
      } else {
        setError("root.serverError", {
          type: "manual",
          message: t("rules.deduplication.messages.unexpectedError"),
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
          <Dialog.Title className="font-bold" as={Title}>
            {selectedDeduplicationRule
              ? `${t("rules.deduplication.form.editRule")} ${selectedDeduplicationRule.name}`
              : t("rules.deduplication.form.addRule")}
            {selectedDeduplicationRule?.default && (
              <Badge className="ml-2" color="orange">
                {t("rules.deduplication.form.defaultRuleBadge")}
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
            title={t("rules.deduplication.form.editingDefaultRule.title")}
            icon={ExclamationTriangleIcon}
            color="orange"
          >
            {t("rules.deduplication.form.editingDefaultRule.message")}
            <br></br>
            <a
              href={`${
                config?.KEEP_DOCS_URL || "https://docs.keephq.dev"
              }/overview/deduplication`}
              target="_blank"
              className="text-orange-600 hover:underline mt-4"
            >
              {t("rules.deduplication.form.editingDefaultRule.learnMore")}
            </a>
          </Callout>
        </div>
      )}

      {selectedDeduplicationRule?.is_provisioned && (
        <div className="flex flex-col">
          <Callout
            className="mb-4 py-8"
            title={t("rules.deduplication.form.editingProvisionedRule.title")}
            icon={ExclamationTriangleIcon}
            color="orange"
          >
            <Text>
              {t("rules.deduplication.form.editingProvisionedRule.message")}
            </Text>
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
                  {t("rules.deduplication.form.ruleName")}
                </Text>
                <Controller
                  name="name"
                  control={control}
                  rules={{ required: t("rules.deduplication.form.validation.ruleNameRequired") }}
                  disabled={!!selectedDeduplicationRule?.is_provisioned}
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
                  {t("rules.deduplication.form.description")}
                </Text>
                <Controller
                  name="description"
                  control={control}
                  rules={{ required: t("rules.deduplication.form.validation.descriptionRequired") }}
                  disabled={!!selectedDeduplicationRule?.is_provisioned}
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
                  {t("rules.deduplication.form.provider")}
                  <span className="ml-1 relative inline-flex items-center">
                    <span className="group relative flex items-center">
                      <Icon
                        icon={InformationCircleIcon}
                        className="w-[1em] h-[1em] text-gray-500"
                      />
                      <span className="absolute bottom-full left-full p-2 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity duration-300 w-80 text-center pointer-events-none group-hover:pointer-events-auto">
                        {t("rules.deduplication.form.providerTooltip")}
                      </span>
                    </span>
                  </span>
                </span>
                <Controller
                  name="provider_type"
                  control={control}
                  rules={{ required: t("rules.deduplication.form.validation.providerRequired") }}
                  render={({ field }) => (
                    <Select
                      {...field}
                      isDisabled={
                        !!selectedDeduplicationRule?.default ||
                        selectedDeduplicationRule?.is_provisioned
                      }
                      options={alertProviders
                        .filter((provider) => provider.type !== "keep")
                        .map((provider) => ({
                          value: `${provider.type}_${provider.id}`,
                          label:
                            provider.details?.name || provider.id || "main",
                          logoUrl: `/icons/${provider.type}-icon.png`,
                        }))}
                      placeholder={t("rules.deduplication.form.placeholders.selectProvider")}
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
                  {t("rules.deduplication.form.fingerprintFields")}
                  <span className="ml-1 relative inline-flex items-center">
                    <span className="group relative flex items-center">
                      <Icon
                        icon={InformationCircleIcon}
                        className="w-[1em] h-[1em] text-gray-500"
                      />
                      <span className="absolute bottom-full left-1/2 transform -translate-x-1/2 p-2 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity duration-300 w-80 text-center pointer-events-none group-hover:pointer-events-auto">
                        {t("rules.deduplication.form.fingerprintFieldsTooltip")}
                      </span>
                    </span>
                  </span>
                </span>
                <Controller
                  name="fingerprint_fields"
                  control={control}
                  rules={{
                    required: t("rules.deduplication.form.validation.fingerprintFieldRequired"),
                  }}
                  render={({ field }) => (
                    <Select
                      {...field}
                      isDisabled={!!selectedDeduplicationRule?.is_provisioned}
                      isMulti
                      options={availableFields.map((fieldName) => ({
                        value: fieldName,
                        label: fieldName,
                      }))}
                      placeholder={t("rules.deduplication.form.placeholders.selectFingerprintFields")}
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
                          ? t("rules.deduplication.form.noOptions")
                          : t("rules.deduplication.form.chooseProviderFirst")
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
                <div className="flex items-center space-x-2">
                  <Controller
                    name="full_deduplication"
                    control={control}
                    render={({ field }) => (
                      <Switch
                        disabled={!!selectedDeduplicationRule?.is_provisioned}
                        checked={field.value}
                        onChange={field.onChange}
                      />
                    )}
                  />
                  <Text className="text-sm font-medium text-gray-700 flex items-center">
                    {t("rules.deduplication.form.fullDeduplication")}
                    <span className="ml-1 relative inline-flex items-center">
                      <span className="group relative flex items-center">
                        <Icon
                          icon={InformationCircleIcon}
                          className="w-[1em] h-[1em] text-gray-500"
                        />
                        <span className="absolute bottom-full left-1/2 transform -translate-x-1/2 p-2 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity duration-300 w-80 text-center pointer-events-none group-hover:pointer-events-auto">
                          {t("rules.deduplication.form.fullDeduplicationTooltip")}
                        </span>
                      </span>
                    </span>
                  </Text>
                </div>
              </div>

              {fullDeduplication && (
                <div>
                  <Text className="block text-sm font-medium text-gray-700 mb-2">
                    {t("rules.deduplication.form.ignoreFields")}
                  </Text>
                  <Controller
                    name="ignore_fields"
                    control={control}
                    render={({ field }) => (
                      <Select
                        {...field}
                        isDisabled={!!selectedDeduplicationRule?.is_provisioned}
                        isMulti
                        options={availableFields.map((fieldName) => ({
                          value: fieldName,
                          label: fieldName,
                        }))}
                        placeholder={t("rules.deduplication.form.placeholders.selectIgnoreFields")}
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
              title={t("rules.deduplication.form.saveError")}
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
            {t("common.actions.cancel")}
          </Button>
          <Button
            color="orange"
            type="submit"
            disabled={isSubmitting || selectedDeduplicationRule?.is_provisioned}
          >
            {isSubmitting ? t("rules.deduplication.form.saving") : t("common.actions.save")}
          </Button>
        </div>
      </form>
    </SidePanel>
  );
};

export default DeduplicationSidebar;
