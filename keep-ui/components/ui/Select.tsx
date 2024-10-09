import React from "react";
import Select, {
  components,
  Props as SelectProps,
  GroupBase,
  StylesConfig,
  SingleValueProps,
  OptionProps,
} from "react-select";
import { Badge } from "@tremor/react";
import Image from "next/image";

type OptionType = { value: string; label: string; logoUrl: string };

const customStyles: StylesConfig<OptionType, false> = {
  control: (provided, state) => ({
    ...provided,
    borderColor: state.isFocused ? "orange" : "#ccc",
    "&:hover": {
      borderColor: "orange",
    },
    boxShadow: state.isFocused ? "0 0 0 1px orange" : "none",
    backgroundColor: state.isDisabled
      ? "rgba(255, 165, 0, 0.1)"
      : "transparent",
  }),
  option: (provided, state) => ({
    ...provided,
    backgroundColor: state.isSelected
      ? "transparent"
      : state.isFocused
      ? "rgba(255, 165, 0, 0.1)"
      : "transparent",
    color: state.isSelected ? "black" : "black",
    "&:hover": {
      backgroundColor: "rgba(255, 165, 0, 0.3)",
    },
  }),
  singleValue: (provided, state) => ({
    ...provided,
    color: "black",
    backgroundColor: state.isDisabled
      ? "rgba(255, 165, 0, 0.1)"
      : "transparent",
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

type CustomSelectProps = Omit<
  SelectProps<OptionType, false, GroupBase<OptionType>>,
  "components"
> & {
  components?: {
    Option?: typeof CustomOption;
    SingleValue?: typeof CustomSingleValue;
  };
};

const CustomOption = (
  props: OptionProps<OptionType, false, GroupBase<OptionType>>
) => (
  <components.Option {...props}>
    {props.data.logoUrl ? (
      <>
        <Image
          className="inline-block mr-2"
          alt={props.data.label}
          src={props.data.logoUrl}
          width={24}
          height={24}
        />
        {props.children}
      </>
    ) : (
      <Badge color="orange" size="sm">
        {props.children}
      </Badge>
    )}
  </components.Option>
);

const CustomSingleValue = (
  props: SingleValueProps<OptionType, false, GroupBase<OptionType>>
) => (
  <components.SingleValue {...props}>
    <div className="flex items-center">
      {props.data.logoUrl ? (
        <>
          <Image
            className="inline-block mr-2"
            alt={props.data.label}
            src={props.data.logoUrl}
            width={24}
            height={24}
          />
          {props.children}
        </>
      ) : (
        <Badge color="orange" size="sm">
          {props.children}
        </Badge>
      )}
    </div>
  </components.SingleValue>
);

const customComponents: CustomSelectProps["components"] = {
  Option: CustomOption,
  SingleValue: CustomSingleValue,
};

type StyledSelectProps = SelectProps<
  OptionType,
  false,
  GroupBase<OptionType>
> & {
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
  ...rest
}) => (
  <Select<OptionType, false, GroupBase<OptionType>>
    value={value}
    onChange={onChange}
    options={options}
    placeholder={placeholder}
    styles={customStyles}
    components={customComponents}
    menuPortalTarget={document.body}
    menuPosition="fixed"
    getOptionLabel={getOptionLabel}
    getOptionValue={getOptionValue}
    {...rest}
  />
);

export default StyledSelect as Select;
