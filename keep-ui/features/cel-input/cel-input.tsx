import React, { ChangeEvent, FC, useRef, useState } from "react";
import type { editor } from "monaco-editor";
import { MonacoCelEditor } from "@/shared/ui/MonacoCELEditor";

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
    const [currentValue, setCurrentValue] = useState<string>(value);
    setCurrentValue(value);

    return (
      <div className="flex-1 overflow-hidden h-9 border rounded-md pl-9">
        <MonacoCelEditor
          className="h-20 relative top-1"
          value={currentValue}
          onValueChange={setCurrentValue}
        />
      </div>
    );
};

export default CelInput;
