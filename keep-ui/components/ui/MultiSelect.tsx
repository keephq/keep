import React from "react";
import Select from "react-select";
import {
  components,
  Props as SelectProps,
  GroupBase,
  StylesConfig,
} from "react-select";
import { Badge } from "@tremor/react";

type OptionType = { value: string; label: string };

const customStyles: StylesConfig<OptionType, true> = {
  control: (provided: any, state: any) => ({
    ...provided,
    borderColor: state.isFocused ? "orange" : "#ccc",
    "&:hover": {
      borderColor: "orange",
    },
    boxShadow: state.isFocused ? "0 0 0 1px orange" : null,
    backgroundColor: "transparent",
  }),
  option: (provided, state) => ({
    ...provided,
    backgroundColor: state.isSelected
      ? "orange"
      : state.isFocused
      ? "rgba(255, 165, 0, 0.1)"
      : "transparent",
    color: state.isSelected ? "white" : "black",
    "&:hover": {
      backgroundColor: "rgba(255, 165, 0, 0.3)",
    },
  }),
  multiValue: (provided) => ({
    ...provided,
    backgroundColor: "default",
  }),
  multiValueLabel: (provided) => ({
    ...provided,
    color: "black",
  }),
  multiValueRemove: (provided) => ({
    ...provided,
    color: "orange",
    "&:hover": {
      backgroundColor: "orange",
      color: "white",
    },
  }),
  menuPortal: (base) => ({
    ...base,
    zIndex: 9999,
  }),
  menu: (provided) => ({
    ...provided,
    zIndex: 9999,
  }),
};

type CustomSelectProps = SelectProps<
  OptionType,
  true,
  GroupBase<OptionType>
> & {
  components?: {
    Option?: typeof components.Option;
    MultiValue?: typeof components.MultiValue;
  };
};

const customComponents: CustomSelectProps["components"] = {
  Option: ({ children, ...props }) => (
    <components.Option {...props}>
      <Badge color="orange" size="sm">
        {children}
      </Badge>
    </components.Option>
  ),
  MultiValue: ({ children, ...props }) => (
    <components.MultiValue {...props}>
      <Badge color="orange" size="sm">
        {children}
      </Badge>
    </components.MultiValue>
  ),
};

type MultiSelectProps = SelectProps<OptionType, true, GroupBase<OptionType>>;

const MultiSelect: React.FC<MultiSelectProps> = ({
  value,
  onChange,
  options,
  placeholder,
  ...rest
}) => (
  <Select
    isMulti
    value={value}
    onChange={onChange}
    options={options}
    placeholder={placeholder}
    styles={customStyles}
    components={customComponents}
    menuPortalTarget={document.body}
    menuPosition="fixed"
    {...rest}
  />
);

export default MultiSelect;
