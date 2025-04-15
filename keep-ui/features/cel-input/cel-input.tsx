import { MonacoEditor } from "@/shared/ui";
import React, { ChangeEvent, FC, useState } from "react";

interface CelInputProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

const CelInput: FC<CelInputProps> = ({
  value = "",
  onChange,
  placeholder = "Enter value",
  disabled = false,
}) => {
  const [inputValue, setInputValue] = useState(value);

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    const newValue = event.target.value;
    setInputValue(newValue);
    if (onChange) {
      onChange(newValue);
    }
  };

  return (
    // <input
    //   type="text"
    //   value={inputValue}
    //   onChange={handleChange}
    //   placeholder={placeholder}
    //   disabled={disabled}
    //   className="cel-input"
    // />

    <MonacoEditor
      // value={JSON.stringify(eventData, null, 2)}
      language="cel"
      defaultLanguage="cel"
      theme="vs-light"
      className="h-10"
      options={{
        readOnly: false,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontSize: 12,
        lineNumbers: "off",
        folding: false,
        wordWrap: "off",
      }}
    />
  );
};

export default CelInput;
