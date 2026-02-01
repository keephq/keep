import { TextInput } from "@/components/ui";
import { useEffect, useState } from "react";

interface SearchInputProps {
  className?: string;
  value?: string;
  placeholder: string;
  onValueChange: (value: string) => void;
}

export const SearchInput = ({
  className,
  placeholder,
  onValueChange,
  value,
}: SearchInputProps) => {
  const [inputValue, setInputValue] = useState("");

  useEffect(() => {
    const timeoutId = setTimeout(() => onValueChange(inputValue), 500);
    return () => clearTimeout(timeoutId);
  }, [inputValue, onValueChange]);

  useEffect(() => setInputValue(value || ""), [value]);

  return (
    <TextInput
      className={className}
      placeholder={placeholder}
      value={inputValue}
      onValueChange={setInputValue}
    />
  );
};
