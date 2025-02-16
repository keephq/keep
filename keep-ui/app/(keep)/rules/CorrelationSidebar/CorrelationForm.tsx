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

type CorrelationFormProps = {
  alertsFound: AlertDto[];
  isLoading: boolean;
};

export const CorrelationForm = ({
  alertsFound = [],
  isLoading,
}: CorrelationFormProps) => {
  const {
    control,
    register,
    formState: { errors, isSubmitted },
  } = useFormContext<CorrelationFormType>();

  const getNestedKeys = (obj: any, prefix = ""): string[] => {
    return Object.entries(obj).reduce<string[]>((acc, [key, value]) => {
      const newKey = prefix ? `${prefix}.${key}` : key;
      if (value && typeof value === "object" && !Array.isArray(value)) {
        return [...acc, ...getNestedKeys(value, newKey)];
      }
      return [...acc, newKey];
    }, []);
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
          Correlation name <span className="text-red-500">*</span>
          <TextInput
            type="text"
            placeholder="Correlation rule name"
            className="mt-2"
            {...register("name", {
              required: { message: "Name is required", value: true },
            })}
            error={isSubmitted && !!get(errors, "name.message")}
            errorMessage={isSubmitted && get(errors, "name.message")}
          />
        </label>

        <span className="grid grid-cols-2 gap-x-2">
          <legend className="text-tremor-default font-medium text-tremor-content-strong flex items-center col-span-2">
            Append to the same Incident if delay between alerts is below{" "}
            <Button
              className="cursor-default ml-2"
              type="button"
              tooltip="When the first alert arrives, Keep calculates the timespan. Any new alert within this timeframe will correlate into the same incident. The timeframe cannot exceed 14 days."
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
                <SelectItem value="seconds">Seconds</SelectItem>
                <SelectItem value="minutes">Minutes</SelectItem>
                <SelectItem value="hours">Hours</SelectItem>
                <SelectItem value="days">Days</SelectItem>
              </Select>
            )}
          />
        </span>
      </fieldset>
      <fieldset className="grid grid-cols-1">
        <div>
          <label className="text-tremor-default mr-10 font-medium text-tremor-content-strong flex items-center">
            Incident name template
            <Button
              className="cursor-default ml-2"
              type="button"
              tooltip="You can use alert fields in the template by wrapping them in curly braces, e.g. 'Incident on hosts {{ alert.host }}'. With two alerts from hosts 'host1' and 'host2', the incident name would be 'Incident on hosts host1, host2'. Default: correlation rule name will be used."
              icon={QuestionMarkCircleIcon}
              size="xs"
              variant="light"
              color="slate"
            />
          </label>
          <TextInput
            type="text"
            placeholder="Use Keep's expressions to create the incident name, for example: 'Incident on hosts {{ alert.host }}' will create an incident name like 'Incident on hosts host1, host2'. Default: correlation rule name will be used."
            className="mt-2"
            {...register("incidentNameTemplate", {
              required: {
                message: "Incident name template is required",
                value: true,
              },
            })}
            error={isSubmitted && !!get(errors, "incidentNameTemplate.message")}
            errorMessage={
              isSubmitted && get(errors, "incidentNameTemplate.message")
            }
          />
        </div>
      </fieldset>

      <fieldset className="grid grid-cols-3">
        <div className="mr-10">
          <label
            className="flex items-center text-tremor-default font-medium text-tremor-content-strong"
            htmlFor="groupedAttributes"
          >
            Select attribute(s) to group by{" "}
            {keys.length < 1 && (
              <Button
                className="cursor-default ml-2"
                type="button"
                tooltip="Attributes are used to distinguish between incidents. For example, grouping by 'host' will correlate alerts with hostX and hostY into separate incidents. Attributes cannot be calculated without alerts."
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
            Resolve on{" "}
          </label>

          <Controller
            control={control}
            name="resolveOn"
            render={({ field: { value, onChange } }) => (
              <Select value={value} onValueChange={onChange} className="mt-2">
                <SelectItem value="never">No auto-resolution</SelectItem>
                <SelectItem value="all_resolved">
                  All alerts resolved
                </SelectItem>
                <SelectItem value="first_resolved">
                  First alert resolved
                </SelectItem>
                <SelectItem value="last_resolved">
                  Last alert resolved
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
            Start incident on{" "}
          </label>

          <Controller
            control={control}
            name="createOn"
            render={({ field: { value, onChange } }) => (
              <Select value={value} onValueChange={onChange} className="mt-2">
                <SelectItem value="any">Any condition met</SelectItem>
                <SelectItem value="all">All conditions met</SelectItem>
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
          <Text>Created incidents require manual approve</Text>
        </label>
      </div>
    </div>
  );
};
