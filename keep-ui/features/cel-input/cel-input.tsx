import React, { ChangeEvent, FC, useRef, useState } from "react";
import type { editor } from "monaco-editor";
import { MonacoCelEditor } from "@/shared/ui/MonacoCELEditor";

interface CelInputProps {
  value?: string;
  onValueChange?: (value: string) => void;
  onKeyDown?: (e: KeyboardEvent) => void;
  onFocus?: () => void;
  placeholder?: string;
  disabled?: boolean;
}

const CelInput: FC<CelInputProps> = ({
  value = "",
  onValueChange,
  onKeyDown,
  onFocus,
  placeholder = "Enter value",
  disabled = false,
}) => {
  return (
    <div className="flex-1 h-9 border rounded-md pl-9">
      <MonacoCelEditor
        className="h-20 relative top-1"
        value={value}
        onValueChange={onValueChange || ((value: string) => {})}
        onKeyDown={onKeyDown}
        onFocus={onFocus}
      />
    </div>
  );
};

export default CelInput;
