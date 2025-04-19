import React, { ChangeEvent, FC, useRef, useState } from "react";
import type { editor } from "monaco-editor";
import { MonacoCelEditor } from "@/shared/ui/MonacoCELEditor";

interface CelInputProps {
  value?: string;
  fieldsForSuggestions?: string[];
  onValueChange?: (value: string) => void;
  onKeyDown?: (e: KeyboardEvent) => void;
  onFocus?: () => void;
  placeholder?: string;
  disabled?: boolean;
}

const CelInput: FC<CelInputProps> = ({
  value = "",
  fieldsForSuggestions = [],
  onValueChange,
  onKeyDown,
  onFocus,
  placeholder = "Enter value",
  disabled = false,
}) => {
  return (
    <div className="flex-1 h-9 border rounded-md pl-9 relative bg-white">
      {placeholder && !value && (
        <div className="absolute top-0 w-full h-full flex items-center text-sm text-gray-900 text-opacity-50">
          {placeholder}
        </div>
      )}
      <MonacoCelEditor
        className="h-20 relative top-1 {}"
        value={value}
        fieldsForSuggestions={fieldsForSuggestions}
        onValueChange={onValueChange || ((value: string) => {})}
        onKeyDown={onKeyDown}
        onFocus={onFocus}
      />
    </div>
  );
};

export default CelInput;
