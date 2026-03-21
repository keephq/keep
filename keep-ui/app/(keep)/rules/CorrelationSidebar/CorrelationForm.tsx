import { useI18n } from "@/i18n/hooks/useI18n";
import {
  Button,
  MultiSelect,
  MultiSelectItem,
  NumberInput,
  Select,
  SelectItem,
  Switch,
  Text,
  TextInput,
} from "@tremor/react";
import { Controller, get, useFormContext } from "react-hook-form";
import { AlertDto } from "@/entities/alerts/model";
import { QuestionMarkCircleIcon } from "@heroicons/react/24/outline";
import React from "react";
import { CorrelationFormType } from "./types";
import { useTenantConfiguration } from "@/utils/hooks/useTenantConfiguration";
import { useUsers } from "@/entities/users/model/useUsers";
import { Input } from "@/shared/ui";

type CorrelationFormProps = {
  alertsFound: AlertDto[];
  isLoading: boolean;
};

export const CorrelationForm = ({
  alertsFound = [],
  isLoading,
}: CorrelationFormProps) => {
  const { t } = useI18n();
  const {
    control,
    register,
    watch,
    formState: { errors, isSubmitted },
  } = useFormContext<CorrelationFormType>();

  const { data: tenantConfiguration } = useTenantConfiguration();
  const { data: users = [] } = useUsers();

  const getNestedKeys = (obj: any, prefix = ""): string[] => {
    return Object.entries(obj).reduce<string[]>((acc, [key, value]) => {
      const newKey = prefix ? `${prefix}.${key}` : key;
      if (value && typeof value === "object" && !Array.isArray(value)) {
        return [...acc, newKey, ...getNestedKeys(value, newKey)];
      }
      return [...acc, newKey];
    }, []);
  };

  const getMultiLevelKeys = (obj: AlertDto, groupBy: string): string[] => {
    if (!obj || !groupBy) return [];
    const objAsAny = obj as any;
    const key = Object.keys(objAsAny[groupBy])[0];
    return Object.keys(objAsAny[groupBy][key]);
  };

  const keys = [
    ...alertsFound.reduce<Set<string>>((acc, alert) => {
      const alertKeys = getNestedKeys(alert);
      return new Set([...acc, ...alertKeys]);
    }, new Set<string>()),
  ];

  return (
    <div className="flex flex-col gap-y-4 flex-1">
      <fieldset className="grid grid-cols-2">
        <label className="text-tremor-default mr-10 font-medium text-tremor-content-strong">
          {t("correlation.form.correlationName")} <span className="text-red-500">*</span>
          <TextInput
            type="text"
            placeholder={t("correlation.form.namePlaceholder")}
            className="mt-2"
            {...register("name", {
              required: { message: t("correlation.form.nameRequired"), value: true },
            })}
            error={isSubmitted && !!get(errors, "name.message")}
            errorMessage={isSubmitted && get(errors, "name.message")}
          />
        </label>

        <span className="grid grid-cols-2 gap-x-2">
          <legend
            className="text-tremor-default font-medium text-tremor-content-strong flex items-center col-span-2 truncate"
            title={t("correlation.form.appendIncident")}
          >
            {t("correlation.form.appendIncident")}{" "}
            <Button
              className="cursor-default ml-2"
              type="button"
              tooltip={t("correlation.form.appendIncidentTooltip")}
              icon={QuestionMarkCircleIcon}
              size="xs"
              variant="light"
              color="slate"
            />
          </legend>

          <NumberInput
            defaultValue={5}
            min={1}
            className="mt-2"
            {...register("timeAmount", { validate: (value) => value > 0 })}
          />
          <Controller
            control={control}
            name="timeUnit"
            render={({ field: { value, onChange } }) => (
              <Select value={value} onValueChange={onChange} className="mt-2">
                <SelectItem value="seconds">{t("correlation.form.seconds")}</SelectItem>
                <SelectItem value="minutes">{t("correlation.form.minutes")}</SelectItem>
                <SelectItem value="hours">{t("correlation.form.hours")}</SelectItem>
                <SelectItem value="days">{t("correlation.form.days")}</SelectItem>
              </Select>
            )}
          />
        </span>
      </fieldset>
      <fieldset className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-tremor-default mr-10 font-medium text-tremor-content-strong flex items-center">
            {t("correlation.form.incidentNameTemplate")}
            <Button
              className="cursor-default ml-2"
              type="button"
              tooltip={t("correlation.form.incidentNameTemplateTooltip")}
              icon={QuestionMarkCircleIcon}
              size="xs"
              variant="light"
              color="slate"
            />
          </label>
          <TextInput
            type="text"
            placeholder={t("correlation.form.incidentNameTemplatePlaceholder")}
            className="mt-2"
            {...register("incidentNameTemplate", {
              required: {
                message: t("correlation.form.incidentNameRequired"),
                value: false,
              },
            })}
            error={isSubmitted && !!get(errors, "incidentNameTemplate.message")}
            errorMessage={
              isSubmitted && get(errors, "incidentNameTemplate.message")
            }
          />
        </div>
        <div>
          <label className="text-tremor-default mr-10 font-medium text-tremor-content-strong flex items-center">
            {t("correlation.form.incidentPrefix")}
            <Button
              className="cursor-default ml-2"
              type="button"
              tooltip={t("correlation.form.incidentPrefixTooltip")}
              icon={QuestionMarkCircleIcon}
              size="xs"
              variant="light"
              color="slate"
            />
          </label>
          <TextInput
            type="text"
            placeholder={t("correlation.form.incidentPrefixPlaceholder")}
            className="mt-2"
            {...register("incidentPrefix", {
              required: {
                message: t("correlation.form.incidentPrefixRequired"),
                value: false,
              },
              validate: (value) => {
                if (!value) return true;
                if (value.length > 10) {
                  return t("correlation.form.incidentPrefixTooLong");
                }
                if (!/^[a-zA-Z0-9]+$/.test(value)) {
                  return t("correlation.form.incidentPrefixInvalid");
                }
                return true;
              },
            })}
            error={isSubmitted && !!get(errors, "incidentPrefix.message")}
            errorMessage={isSubmitted && get(errors, "incidentPrefix.message")}
          />
        </div>
      </fieldset>

      <fieldset className="grid grid-cols-3">
        <div className="mr-10">
          <label
            className="flex items-center text-tremor-default font-medium text-tremor-content-strong truncate"
            htmlFor="groupedAttributes"
            title={t("correlation.form.groupByTooltip")}
          >
            {t("correlation.form.groupByAttributes")}{" "}
            {keys.length < 1 && (
              <Button
                className="cursor-default ml-2"
                type="button"
                tooltip={t("correlation.form.groupByTooltip")}
                icon={QuestionMarkCircleIcon}
                size="xs"
                variant="light"
                color="slate"
              />
            )}
          </label>
          <Controller
            control={control}
            name="groupedAttributes"
            render={({ field: { value, onChange } }) => (
              <MultiSelect
                className="mt-2"
                value={value}
                onValueChange={onChange}
                disabled={isLoading || !keys.length}
              >
                {keys.map((alertKey) => (
                  <MultiSelectItem key={alertKey} value={alertKey}>
                    {alertKey}
                  </MultiSelectItem>
                ))}
              </MultiSelect>
            )}
          />
        </div>

        <div className="mr-10">
          <label
            className="flex items-center text-tremor-default font-medium text-tremor-content-strong"
            htmlFor="resolveOn"
          >
            {t("correlation.form.resolveOn")}{" "}
          </label>

          <Controller
            control={control}
            name="resolveOn"
            render={({ field: { value, onChange } }) => (
              <Select value={value} onValueChange={onChange} className="mt-2">
                <SelectItem value="never">{t("correlation.form.noAutoResolution")}</SelectItem>
                <SelectItem value="all_resolved">
                  {t("correlation.form.allAlertsResolved")}
                </SelectItem>
                <SelectItem value="first_resolved">
                  {t("correlation.form.firstAlertResolved")}
                </SelectItem>
                <SelectItem value="last_resolved">
                  {t("correlation.form.lastAlertResolved")}
                </SelectItem>
              </Select>
            )}
          />
        </div>

        <div>
          <label
            className="flex items-center text-tremor-default font-medium text-tremor-content-strong"
            htmlFor="resolveOn"
          >
            {t("correlation.form.startIncidentOn")}{" "}
          </label>

          <Controller
            control={control}
            name="createOn"
            render={({ field: { value, onChange } }) => (
              <Select value={value} onValueChange={onChange} className="mt-2">
                <SelectItem value="any">{t("correlation.form.anyConditionMet")}</SelectItem>
                <SelectItem value="all">{t("correlation.form.allConditionsMet")}</SelectItem>
              </Select>
            )}
          />
        </div>

        <div>
          <label
            className="flex items-center text-tremor-default font-medium text-tremor-content-strong mt-1"
            htmlFor="threshold"
          >
            {t("correlation.form.alertsThreshold")}{" "}
          </label>

          <Controller
            control={control}
            name="threshold"
            render={({ field: { value, onChange } }) => (
              <Input
                type="number"
                placeholder={t("correlation.form.thresholdPlaceholder")}
                className="mt-2"
                {...register("threshold", {
                  required: {
                    message: t("correlation.form.thresholdRequired"),
                    value: false,
                  },
                  validate: (value) => {
                    if (value <= 0) {
                      return t("correlation.form.thresholdPositive");
                    }
                    return true;
                  },
                })}
              />
            )}
          />
        </div>

        <div className="ml-2.5">
          <label
            className="flex items-center text-tremor-default font-medium text-tremor-content-strong mt-1"
            htmlFor="assignee"
          >
            {t("correlation.form.autoAssignToUser")}{" "}
          </label>

          <Controller
            control={control}
            name="assignee"
            render={({ field: { value, onChange } }) => (
              <Select
                value={value || ""}
                onValueChange={onChange}
                className="mt-2"
              >
                <SelectItem value="">{t("correlation.form.noAssignment")}</SelectItem>
                {users.map((user) => (
                  <SelectItem key={user.email} value={user.email}>
                    {user.name || user.email}
                  </SelectItem>
                ))}
              </Select>
            )}
          />
        </div>
      </fieldset>

      <div className="flex items-center space-x-2">
        <Controller
          control={control}
          name="requireApprove"
          render={({ field: { value, onChange } }) => (
            <Switch
              color="orange"
              id="requireManualApprove"
              onChange={onChange}
              checked={value}
            />
          )}
        />

        <label htmlFor="requireManualApprove" className="text-sm text-gray-500">
          <Text>{t("correlation.form.requireManualApprove")}</Text>
        </label>
      </div>
      {tenantConfiguration?.["multi_level_enabled"] && (
        <div className="flex items-center space-x-2">
          <Controller
            control={control}
            name="multiLevel"
            render={({ field: { value, onChange } }) => (
              <Switch
                color="orange"
                id="multiLevelCorrelation"
                onChange={onChange}
                checked={value}
              />
            )}
          />

          <label
            htmlFor="multiLevelCorrelation"
            className="text-sm text-gray-500"
          >
            <Text>{t("correlation.form.multiLevelCorrelation")}</Text>
          </label>
        </div>
      )}
      {watch("multiLevel") && tenantConfiguration?.["multi_level_enabled"] && (
        <div>
          <label className="text-tremor-default mr-10 font-medium text-tremor-content-strong flex items-center">
            {t("correlation.form.multiLevelPropertyName")}
            <span className="text-red-500 ml-1">*</span>
            <Button
              className="cursor-default ml-2"
              type="button"
              tooltip={t("correlation.form.multiLevelPropertyNameTooltip")}
              icon={QuestionMarkCircleIcon}
              size="xs"
              variant="light"
              color="slate"
            />
          </label>
          <Controller
            control={control}
            name="multiLevelPropertyName"
            render={({ field: { value, onChange } }) => (
              <Select value={value} onValueChange={onChange} className="mt-2">
                {getMultiLevelKeys(
                  alertsFound[0],
                  watch("groupedAttributes")[0]
                ).map((key) => (
                  <SelectItem key={key} value={key}>
                    {key}
                  </SelectItem>
                ))}
              </Select>
            )}
          />
        </div>
      )}
    </div>
  );
};
