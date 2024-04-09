import {
  MultiSelect,
  MultiSelectItem,
  NumberInput,
  Select,
  SelectItem,
  TextInput,
  Textarea,
} from "@tremor/react";
import { Controller, get, useFormContext } from "react-hook-form";
import { CorrelationForm as CorrelationFormType } from ".";

export const CorrelationForm = () => {
  const { control, register, formState } =
    useFormContext<CorrelationFormType>();
  const { errors } = formState;

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
      <label className="text-tremor-default font-medium text-tremor-content-strong">
        Description
        <Textarea
          placeholder="Type here..."
          className="mt-2"
          {...register("description", {
            required: { message: "Description is required", value: true },
          })}
          error={!!get(errors, "description.message")}
          errorMessage={get(errors, "description.message")}
        />
      </label>
      <fieldset>
        <legend className="text-tremor-default font-medium text-tremor-content-strong">
          Scan every
        </legend>
        <span className="grid grid-cols-2 mt-2 gap-x-2">
          <NumberInput defaultValue={5} min={1} {...register("timeAmount")} />
          <Controller
            control={control}
            name="timeUnit"
            render={({ field: { value, onChange } }) => (
              <Select value={value} onChange={onChange}>
                <SelectItem value="seconds">Seconds</SelectItem>
                <SelectItem value="minutes">Minutes</SelectItem>
                <SelectItem value="hours">Hours</SelectItem>
                <SelectItem value="days">Days</SelectItem>
              </Select>
            )}
          />
        </span>
      </fieldset>
      <label className="text-tremor-default font-medium text-tremor-content-strong hidden">
        When all condition meets set alert severity to
        <Select className="mt-2" name="severity">
          <SelectItem value="low">Low</SelectItem>
          <SelectItem value="medium">Medium</SelectItem>
          <SelectItem value="high">High</SelectItem>
          <SelectItem value="critical">Critical</SelectItem>
        </Select>
      </label>
      <label className="text-tremor-default font-medium text-tremor-content-strong">
        Select attribute(s) to group by
        <Controller
          control={control}
          name="groupedAttributes"
          render={({ field: { value, onChange } }) => (
            <MultiSelect className="mt-2" value={value} onChange={onChange}>
              <MultiSelectItem value="low">Low</MultiSelectItem>
              <MultiSelectItem value="medium">Medium</MultiSelectItem>
              <MultiSelectItem value="high">High</MultiSelectItem>
              <MultiSelectItem value="critical">Critical</MultiSelectItem>
            </MultiSelect>
          )}
        />
      </label>
    </div>
  );
};
