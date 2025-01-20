"use client";

import ReactSelect, {
  components,
  GroupBase,
  OptionProps,
  Props as SelectProps,
  SingleValueProps,
  StylesConfig,
} from "react-select";
import Image from "next/image";

type OptionType = { value: string; label: string; logoUrl?: string };

const CustomSingleValue = (
  props: SingleValueProps<OptionType, false, GroupBase<OptionType>>
) => (
  <components.SingleValue {...props}>
    <div className="flex items-center">
      {props.data.logoUrl && (
        <Image
          className="inline-block mr-2"
          alt={props.data.label}
          src={props.data.logoUrl}
          width={24}
          height={24}
        />
      )}
      {props.children}
    </div>
  </components.SingleValue>
);

const CustomOption = (
  props: OptionProps<OptionType, false, GroupBase<OptionType>>
) => (
  <components.Option {...props}>
    <div className="flex items-center">
      {props.data.logoUrl && (
        <Image
          className="inline-block mr-2"
          alt={props.data.label}
          src={props.data.logoUrl}
          width={24}
          height={24}
        />
      )}
      {props.children}
    </div>
  </components.Option>
);

const customComponents = {
  Option: CustomOption as any,
  SingleValue: CustomSingleValue as any,
};

interface SelectProps2<
  Option,
  IsMulti extends boolean,
  Group extends GroupBase<Option>,
> extends SelectProps<Option, IsMulti, Group> {
  backgroundColor?: string;
  optionColor?: string;
}

export function Select<
  Option = OptionType,
  IsMulti extends boolean = false,
  Group extends GroupBase<Option> = GroupBase<Option>,
>({
  backgroundColor = "white",
  optionColor = "black",
  ...props
}: SelectProps2<Option, IsMulti, Group>) {
  const customSelectStyles: StylesConfig<Option, IsMulti, Group> = {
    control: (provided, state) => ({
      ...provided,
      borderColor: state.isFocused ? "orange" : "rgb(229 231 235)",
      borderRadius: "0.5rem",
      "&:hover": { borderColor: "orange" },
      boxShadow: state.isFocused ? "0 0 0 1px orange" : provided.boxShadow,
      backgroundColor,
    }),
    singleValue: (provided) => ({
      ...provided,
      display: "flex",
      alignItems: "center",
      color: optionColor,
    }),
    option: (provided, state) => ({
      ...provided,
      backgroundColor: state.isSelected
        ? "orange"
        : state.isFocused
        ? "rgba(255, 165, 0, 0.1)"
        : "transparent",
      color: state.isSelected ? "white" : optionColor,
      "&:hover": state.isSelected
        ? {}
        : {
            backgroundColor: "rgba(255, 165, 0, 0.3)",
          },
    }),
    multiValue: (provided) => ({
      ...provided,
      backgroundColor: "rgb(255 165 0 / 0.1)",
      borderRadius: "0.25rem",
      border: "1px solid rgb(249 115 22 / 0.2)",
    }),
    multiValueLabel: (provided) => ({
      ...provided,
      padding: "0.1rem 0.25rem",
      paddingLeft: "0.5rem",
      color: optionColor,
    }),
    multiValueRemove: (provided) => ({
      ...provided,
      color: "rgb(234 88 12)",
      "&:hover": {
        backgroundColor: "rgb(234 88 12)",
        color: "white",
      },
    }),
    menu: (provided) => ({
      ...provided,
      color: "orange",
      zIndex: 21,
    }),
    menuList: (provided) => ({
      ...provided,
      padding: 0,
    }),
    menuPortal: (base) => ({
      ...base,
      zIndex: 21,
    }),
  };

  return (
    <ReactSelect
      components={customComponents}
      styles={customSelectStyles}
      {...props}
    />
  );
}
