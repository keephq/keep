import React from "react";
import CreatableSelect from "react-select/creatable";
import { components, Props as SelectProps } from "react-select";
import { Badge } from "@tremor/react";

type OptionType = { value: string; label: string };

const customStyles = {
  control: (provided, state) => ({
    ...provided,
    borderColor: state.isFocused ? 'orange' : '#ccc',
    '&:hover': {
      borderColor: 'orange',
    },
    boxShadow: state.isFocused ? '0 0 0 1px orange' : null,
    backgroundColor: 'transparent',
  }),
  option: (provided, state) => ({
    ...provided,
    backgroundColor: state.isSelected ? 'orange' : state.isFocused ? 'rgba(255, 165, 0, 0.1)' : 'transparent',
    color: state.isSelected ? 'white' : 'black',
    '&:hover': {
      backgroundColor: 'rgba(255, 165, 0, 0.3)',
    },
  }),
  multiValue: (provided) => ({
    ...provided,
    backgroundColor: 'default',  // Default background color for multi-value selections
  }),
  multiValueLabel: (provided) => ({
    ...provided,
    color: 'black',
  }),
  multiValueRemove: (provided) => ({
    ...provided,
    color: 'orange',
    '&:hover': {
      backgroundColor: 'orange',
      color: 'white',
    },
  }),
  menuPortal: (base) => ({
    ...base,
    zIndex: 9999, // Ensure the menu appears on top of the modal
  }),
  menu: (provided) => ({
    ...provided,
    zIndex: 9999, // Ensure the menu appears on top of the modal
  }),
};

type CustomSelectProps = SelectProps<OptionType, true> & {
  components?: {
    Option?: typeof components.Option;
    MultiValue?: typeof components.MultiValue;
  };
};

const customComponents: CustomSelectProps['components'] = {
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

const CreatableMultiSelect = ({ value, onChange, onCreateOption, options, placeholder }: SelectProps<OptionType, true>) => (
  <CreatableSelect
    isMulti
    value={value}
    onChange={onChange}
    onCreateOption={onCreateOption}
    options={options}
    placeholder={placeholder}
    styles={customStyles}
    components={customComponents}
    menuPortalTarget={document.body} // Render the menu in a portal
    menuPosition="fixed"
  />
);

export default CreatableMultiSelect;
