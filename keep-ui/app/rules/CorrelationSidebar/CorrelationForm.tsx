import {
  Button,
  MultiSelect,
  MultiSelectItem,
  NumberInput,
  Select,
  SelectItem,
  TextInput,
} from "@tremor/react";
import { Controller, get, useFormContext } from "react-hook-form";
import { CorrelationForm as CorrelationFormType } from ".";
import { AlertDto } from "app/alerts/models";
import { QuestionMarkCircleIcon } from "@heroicons/react/24/outline";

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
      const alertKeys = Object.keys(alert);

      return new Set([...acc, ...alertKeys]);
    }, new Set<string>()),
  ];

  return (
    <div className="flex flex-col gap-y-4 flex-1">
      <label className="text-tremor-default font-medium text-tremor-content-strong">
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
      <fieldset>
        <legend className="text-tremor-default font-medium text-tremor-content-strong flex items-center">
          Scan every{" "}
          <Button
            className="cursor-default ml-2"
            type="button"
            tooltip="Time cannot exceed 14 days"
            icon={QuestionMarkCircleIcon}
            size="xs"
            variant="light"
            color="slate"
          />
        </legend>
        <span className="grid grid-cols-2 mt-2 gap-x-2">
          <NumberInput
            defaultValue={5}
            min={1}
            {...register("timeAmount", { validate: (value) => value > 0 })}
          />
          <Controller
            control={control}
            name="timeUnit"
            render={({ field: { value, onChange } }) => (
              <Select value={value} onValueChange={onChange}>
                <SelectItem value="seconds">Seconds</SelectItem>
                <SelectItem value="minutes">Minutes</SelectItem>
                <SelectItem value="hours">Hours</SelectItem>
                <SelectItem value="days">Days</SelectItem>
              </Select>
            )}
          />
        </span>
      </fieldset>
      <div>
        <label
          className="flex items-center text-tremor-default font-medium text-tremor-content-strong"
          htmlFor="groupedAttributes"
        >
          Select attribute(s) to group by{" "}
          {keys.length < 1 && (
            <Button
              className="cursor-default ml-2"
              type="button"
              tooltip="You cannot calculate attributes to group by without alerts"
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
    </div>
  );
};
