import { TextInput } from "@/components/ui";
import { useEffect, useState } from "react";

interface SearchInputProps {
  className?: string;
  placeholder: string;
  onValueChange: (value: string) => void;
}

export const SearchInput = ({
  className,
  placeholder,
  onValueChange,
}: SearchInputProps) => {
  const [inputValue, setInputValue] = useState("");

  useEffect(() => {
    const timeoutId = setTimeout(() => onValueChange(inputValue), 500);
    return () => clearTimeout(timeoutId);
  }, [inputValue]);

  return (
    <TextInput
      className={className}
      placeholder={placeholder}
      onValueChange={setInputValue}
    />
  );
};
