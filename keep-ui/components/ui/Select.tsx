import React from "react";
import Select, { components, Props as SelectProps, GroupBase, StylesConfig } from "react-select";
import { Badge } from "@tremor/react";

type OptionType = { value: string; label: string };

const customStyles: StylesConfig<OptionType, false> = {
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
    backgroundColor: state.isSelected ? 'transparent' : state.isFocused ? 'rgba(255, 165, 0, 0.1)' : 'transparent',
    color: state.isSelected ? 'white' : 'black',
    '&:hover': {
      backgroundColor: 'rgba(255, 165, 0, 0.3)',
    },
  }),
  singleValue: (provided) => ({
    ...provided,
    color: 'black',
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

type CustomSelectProps = SelectProps<OptionType, false, GroupBase<OptionType>> & {
  components?: {
    Option?: typeof components.Option;
    SingleValue?: typeof components.SingleValue;
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
  SingleValue: ({ children, ...props }) => (
    <components.SingleValue {...props}>
      <Badge color="orange" size="sm">
        {children}
      </Badge>
    </components.SingleValue>
  ),
};

type StyledSelectProps = SelectProps<OptionType, false, GroupBase<OptionType>> & {
  getOptionLabel?: (option: OptionType) => string;
  getOptionValue?: (option: OptionType) => string;
};

const StyledSelect: React.FC<StyledSelectProps> = ({
  value,
  onChange,
  options,
  placeholder,
  getOptionLabel,
  getOptionValue,
}) => (
  <Select
    value={value}
    onChange={onChange}
    options={options}
    placeholder={placeholder}
    styles={customStyles}
    components={customComponents}
    menuPortalTarget={document.body} // Render the menu in a portal
    menuPosition="fixed"
    getOptionLabel={getOptionLabel} // Support custom getOptionLabel
    getOptionValue={getOptionValue} // Support custom getOptionValue
  />
);

export default StyledSelect as Select;
