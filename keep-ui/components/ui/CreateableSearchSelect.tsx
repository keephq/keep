import { MagnifyingGlassIcon } from "@radix-ui/react-icons";
import { SearchSelect, SearchSelectItem } from "@tremor/react";
import { useEffect, useState } from "react";

type Props = {
  selectId: string;
  options: string[];
  onFieldChange: (selectId: string, value: string) => void;
  disabled?: boolean;
  defaultValue?: string;
  className: string;
};
export const CreateableSearchSelect = ({
  selectId,
  onFieldChange,
  options,
  disabled,
  className,
  defaultValue = "",
}: Props) => {
  const [fields, setFields] = useState<string[]>([]);
  const [searchValue, setSearchValue] = useState("");

  useEffect(() => {
    setFields(options);
  }, [options]);

  useEffect(() => {
    setSearchValue(defaultValue);
  }, [defaultValue]);

  const onValueChange = (selectedValue: string) => {
    if (searchValue.length) {
      const doesSearchedValueExistInFields = fields.some(
        (name) =>
          name.toLowerCase().trim() === selectedValue.toLowerCase().trim()
      );

      if (doesSearchedValueExistInFields === false) {
        setSearchValue("");
        setFields((fields) => [...fields, selectedValue]);
      }
    }

    onFieldChange(selectId, selectedValue);
  };

  return (
    <SearchSelect
      onValueChange={onValueChange}
      onSearchValueChange={setSearchValue}
      enableClear={false}
      icon={MagnifyingGlassIcon}
      disabled={disabled}
      className={className}
      value={defaultValue}
      required
    >
      {fields.map((option) => (
        <SearchSelectItem key={option} value={option}>
          {option}
        </SearchSelectItem>
      ))}
      {searchValue.trim() && (
        <SearchSelectItem value={searchValue}>{searchValue}</SearchSelectItem>
      )}
    </SearchSelect>
  );
};
