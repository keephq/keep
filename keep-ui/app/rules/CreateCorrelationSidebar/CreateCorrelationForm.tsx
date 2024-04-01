import {
  MultiSelect,
  MultiSelectItem,
  NumberInput,
  Select,
  SelectItem,
  TextInput,
  Textarea,
} from "@tremor/react";

export const CreateCorrelationForm = () => {
  return (
    <div className="flex flex-col gap-y-4">
      <label className="text-tremor-default font-medium text-tremor-content-strong">
        Correlation name
        <TextInput
          type="text"
          name="correlation-name"
          placeholder="Choose name"
          className="mt-2"
          required
        />
      </label>
      <label className="text-tremor-default font-medium text-tremor-content-strong">
        Description
        <Textarea
          name="description"
          placeholder="Type here..."
          className="mt-2"
          required
        />
      </label>
      <fieldset>
        <legend className="text-tremor-default font-medium text-tremor-content-strong">
          Scan every
        </legend>
        <span className="grid grid-cols-2 mt-2 gap-x-2">
          <NumberInput name="time-amount" defaultValue={5} min={1} />
          <Select name="time-units" defaultValue="minutes">
            <SelectItem value="seconds">Seconds</SelectItem>
            <SelectItem value="minutes">Minutes</SelectItem>
            <SelectItem value="hours">Hours</SelectItem>
            <SelectItem value="days">Days</SelectItem>
          </Select>
        </span>
      </fieldset>
      <label className="text-tremor-default font-medium text-tremor-content-strong">
        When all condition meets set alert severity to
        <Select className="mt-2" name="severity" defaultValue="high">
          <SelectItem value="low">Low</SelectItem>
          <SelectItem value="medium">Medium</SelectItem>
          <SelectItem value="high">High</SelectItem>
          <SelectItem value="critical">Critical</SelectItem>
        </Select>
      </label>
      <label className="text-tremor-default font-medium text-tremor-content-strong">
        Select attribute(s) to group by
        <MultiSelect className="mt-2" name="grouped-attributes">
          <MultiSelectItem value="low">Low</MultiSelectItem>
          <MultiSelectItem value="medium">Medium</MultiSelectItem>
          <MultiSelectItem value="high">High</MultiSelectItem>
          <MultiSelectItem value="critical">Critical</MultiSelectItem>
        </MultiSelect>
      </label>
    </div>
  );
};
