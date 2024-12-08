import { useMemo, useRef, useState } from "react";
import {
  Provider,
  ProviderAuthConfig,
  ProviderFormData,
  ProviderFormKVData,
  ProviderFormValue,
  ProviderInputErrors,
} from "./providers";
import {
  Title,
  Text,
  Button,
  Callout,
  Icon,
  Subtitle,
  Divider,
  TextInput,
  Select,
  SelectItem,
  Card,
  Tab,
  TabList,
  TabGroup,
  TabPanel,
  TabPanels,
  Accordion,
  AccordionHeader,
  AccordionBody,
  Badge,
  Switch,
} from "@tremor/react";
import {
  QuestionMarkCircleIcon,
  ArrowLongRightIcon,
  ArrowLongLeftIcon,
  ArrowTopRightOnSquareIcon,
  ArrowDownOnSquareIcon,
  GlobeAltIcon,
  DocumentTextIcon,
  PlusIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";

export function getRequiredConfigs(
  config: Provider["config"]
): Provider["config"] {
  const configs = Object.entries(config).filter(
    ([_, config]) => config.required && !config.config_main_group
  );
  return Object.fromEntries(configs);
}

export function getOptionalConfigs(
  config: Provider["config"]
): Provider["config"] {
  const configs = Object.entries(config).filter(
    ([_, config]) =>
      !config.required && !config.hidden && !config.config_main_group
  );
  return Object.fromEntries(configs);
}

function getConfigGroup(type: "config_main_group" | "config_sub_group") {
  return (configs: Provider["config"]) => {
    return Object.entries(configs).reduce(
      (acc: Record<string, Provider["config"]>, [key, config]) => {
        const group = config[type];
        if (!group) return acc;
        acc[group] ??= {};
        acc[group][key] = config;
        return acc;
      },
      {}
    );
  };
}

export const getConfigByMainGroup = getConfigGroup("config_main_group");
export const getConfigBySubGroup = getConfigGroup("config_sub_group");

export function GroupFields({
  groupName,
  fields,
  data,
  errors,
  disabled,
  onChange,
}: {
  groupName: string;
  fields: Provider["config"];
  data: ProviderFormData;
  errors: ProviderInputErrors;
  disabled: boolean;
  onChange: (key: string, value: ProviderFormValue) => void;
}) {
  const subGroups = useMemo(() => getConfigBySubGroup(fields), [fields]);

  if (Object.keys(subGroups).length === 0) {
    // If no subgroups, render fields directly
    return (
      <Card className="mt-4">
        <Title className="capitalize"> {groupName} </Title>
        {Object.entries(fields).map(([field, config]) => (
          <div className="mt-2.5" key={field}>
            <FormField
              id={field}
              config={config}
              value={data[field]}
              error={errors[field]}
              disabled={disabled}
              onChange={onChange}
            />
          </div>
        ))}
      </Card>
    );
  }

  return (
    <Card className="mt-4">
      <Title className="capitalize">{groupName}</Title>
      <TabGroup className="mt-2">
        <TabList>
          {Object.keys(subGroups).map((name) => (
            <Tab key={name} className="capitalize">
              {name}
            </Tab>
          ))}
        </TabList>
        <TabPanels>
          {Object.entries(subGroups).map(([name, subGroup]) => (
            <TabPanel key={name}>
              {Object.entries(subGroup).map(([field, config]) => (
                <div className="mt-2.5" key={field}>
                  <FormField
                    id={field}
                    config={config}
                    value={data[field]}
                    error={errors[field]}
                    disabled={disabled}
                    onChange={onChange}
                  />
                </div>
              ))}
            </TabPanel>
          ))}
        </TabPanels>
      </TabGroup>
    </Card>
  );
}

export function FormField({
  id,
  config,
  value,
  error,
  disabled,
  title,
  onChange,
}: {
  id: string;
  config: ProviderAuthConfig;
  value: ProviderFormValue;
  error?: string;
  disabled: boolean;
  title?: string;
  onChange: (key: string, value: ProviderFormValue) => void;
}) {
  function handleInputChange(event: React.ChangeEvent<HTMLInputElement>) {
    let value;
    const files = event.target.files;
    const name = event.target.name;

    // If the input is a file, retrieve the file object, otherwise retrieve the value
    if (files && files.length > 0) {
      value = files[0]; // Assumes single file upload
    } else {
      value = event.target.value;
    }

    onChange(name, value);
  }

  switch (config.type) {
    case "select":
      return (
        <SelectField
          id={id}
          config={config}
          value={value}
          error={error}
          disabled={disabled}
          onChange={(value) => onChange(id, value)}
        />
      );
    case "form":
      return (
        <KVForm
          id={id}
          config={config}
          value={value}
          error={error}
          disabled={disabled}
          onAdd={(data) => onChange(id, data)}
          onChange={(value) => onChange(id, value)}
        />
      );
    case "file":
      return (
        <FileField
          id={id}
          config={config}
          error={error}
          disabled={disabled}
          onChange={handleInputChange}
        />
      );
    case "switch":
      return (
        <SwitchInput
          id={id}
          config={config}
          value={value}
          disabled={disabled}
          onChange={(value) => onChange(id, value)}
        />
      );
    default:
      return (
        <TextField
          id={id}
          config={config}
          value={value}
          error={error}
          disabled={disabled}
          title={title}
          onChange={handleInputChange}
        />
      );
  }
}

export function TextField({
  id,
  config,
  value,
  error,
  disabled,
  title,
  onChange,
}: {
  id: string;
  config: ProviderAuthConfig;
  value: ProviderFormValue;
  error?: string;
  disabled: boolean;
  title?: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <>
      <FieldLabel id={id} config={config} />
      <TextInput
        type={config.sensitive ? "password" : "text"}
        id={id}
        name={id}
        value={value?.toString() ?? ""}
        onChange={onChange}
        autoComplete="off"
        error={Boolean(error)}
        errorMessage={error}
        placeholder={config.placeholder ?? `Enter ${id}`}
        disabled={disabled}
        title={title ?? ""}
      />
    </>
  );
}

export function SelectField({
  id,
  config,
  value,
  error,
  disabled,
  onChange,
}: {
  id: string;
  config: ProviderAuthConfig;
  value: ProviderFormValue;
  error?: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <>
      <FieldLabel id={id} config={config} />
      <Select
        name={id}
        value={value?.toString() ?? config.default?.toString()}
        onValueChange={onChange}
        placeholder={config.placeholder || `Select ${id}`}
        error={Boolean(error)}
        errorMessage={error}
        disabled={disabled}
      >
        {config.options?.map((option) => (
          <SelectItem key={option} value={option.toString()}>
            {option}
          </SelectItem>
        ))}
      </Select>
    </>
  );
}

export function FileField({
  id,
  config,
  disabled,
  error,
  onChange,
}: {
  id: string;
  config: ProviderAuthConfig;
  disabled: boolean;
  error?: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  const [selected, setSelected] = useState<string>();
  const ref = useRef<HTMLInputElement>(null);

  function handleClick(e: React.MouseEvent<HTMLButtonElement>) {
    e.preventDefault();
    if (ref.current) ref.current.click();
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files[0]) {
      setSelected(e.target.files[0].name);
    }
    onChange(e);
  }

  return (
    <>
      <FieldLabel id={id} config={config} />
      <Button
        type="button"
        color="orange"
        size="md"
        icon={ArrowDownOnSquareIcon}
        disabled={disabled}
        onClick={handleClick}
      >
        {selected ? `File Chosen: ${selected}` : `Upload a ${id}`}
      </Button>
      <input
        type="file"
        ref={ref}
        id={id}
        name={id}
        accept={config.file_type}
        style={{ display: "none" }}
        onChange={handleChange}
        disabled={disabled}
      />
      {error && error?.length > 0 && (
        <p className="text-sm text-red-500 mt-1">{error}</p>
      )}
    </>
  );
}

export function KVForm({
  id,
  config,
  value,
  error,
  disabled,
  onAdd,
  onChange,
}: {
  id: string;
  config: ProviderAuthConfig;
  value: ProviderFormValue;
  error?: string;
  disabled: boolean;
  onAdd: (data: ProviderFormKVData) => void;
  onChange: (value: ProviderFormKVData) => void;
}) {
  function handleAdd() {
    const newData = Array.isArray(value)
      ? [...value, { key: "", value: "" }]
      : [{ key: "", value: "" }];
    onAdd(newData);
  }

  return (
    <div>
      <div className="flex items-center mb-2">
        <FieldLabel id={id} config={config} />
        <Button
          type="button"
          className="ml-2"
          icon={PlusIcon}
          variant="secondary"
          color="orange"
          size="xs"
          onClick={handleAdd}
          disabled={disabled}
        >
          Add Entry
        </Button>
      </div>
      {Array.isArray(value) && <KVInput data={value} onChange={onChange} />}
      {error && error?.length > 0 && (
        <p className="text-sm text-red-500 mt-1">{error}</p>
      )}
    </div>
  );
}

export const KVInput = ({
  data,
  onChange,
}: {
  data: ProviderFormKVData;
  onChange: (entries: ProviderFormKVData) => void;
}) => {
  const handleEntryChange = (index: number, name: string, value: string) => {
    const newEntries = data.map((entry, i) =>
      i === index ? { ...entry, [name]: value } : entry
    );
    onChange(newEntries);
  };

  const removeEntry = (index: number) => {
    const newEntries = data.filter((_, i) => i !== index);
    onChange(newEntries);
  };

  return (
    <div>
      {data.map((entry, index) => (
        <div key={index} className="flex items-center mb-2">
          <TextInput
            value={entry.key}
            onChange={(e) => handleEntryChange(index, "key", e.target.value)}
            placeholder="Key"
            className="mr-2"
          />
          <TextInput
            value={entry.value}
            onChange={(e) => handleEntryChange(index, "value", e.target.value)}
            placeholder="Value"
            className="mr-2"
          />
          <Button
            type="button"
            icon={TrashIcon}
            variant="secondary"
            color="orange"
            size="xs"
            onClick={() => removeEntry(index)}
          />
        </div>
      ))}
    </div>
  );
};

export function SwitchInput({
  id,
  config,
  value,
  disabled,
  onChange,
}: {
  id: string;
  config: ProviderAuthConfig;
  value: ProviderFormValue;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  if (typeof value !== "boolean") return null;

  return (
    <div className="flex justify-between">
      <FieldLabel id={id} config={config} />
      <Switch checked={value} disabled={disabled} onChange={onChange} />
    </div>
  );
}

export function FieldLabel({
  id,
  config,
}: {
  id: string;
  config: ProviderAuthConfig;
}) {
  return (
    <label htmlFor={id} className="flex items-center mb-1">
      <Text className="capitalize">
        {config.description}
        {config.required === true && <span className="text-red-400">*</span>}
      </Text>
      {config.hint && (
        <Icon
          icon={QuestionMarkCircleIcon}
          variant="simple"
          color="gray"
          size="sm"
          tooltip={`${config.hint}`}
        />
      )}
    </label>
  );
}
