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
  const { control, register, formState } =
    useFormContext<CorrelationFormType>();
  const { errors } = formState;

  const keys = [
    ...alertsFound.reduce<Set<string>>((acc, alert) => {
      const alertKeys: any = Object.keys(alert);

      return new Set([...acc, ...alertKeys]);
    }, new Set<string>()),
  ];

  return (
    <div className="flex flex-col gap-y-4 flex-1">
      <fieldset className="grid grid-cols-2">
        <label className="text-tremor-default mr-10 font-medium text-tremor-content-strong">
          Correlation name
          <TextInput
            type="text"
            placeholder="Choose name"
            className="mt-2"
            {...register("name", {
              required: { message: "Name is required", value: true },
            })}
            error={!!get(errors, "name.message")}
            errorMessage={get(errors, "name.message")}
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
      <fieldset className="grid grid-cols-2">
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

        <div>
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
                <SelectItem value="all">All alerts resolved</SelectItem>
                <SelectItem value="first">First alert resolved</SelectItem>
                <SelectItem value="last">Last alert resolved</SelectItem>
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
