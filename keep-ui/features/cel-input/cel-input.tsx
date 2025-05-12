import React, { ChangeEvent, FC, useRef, useState } from "react";
import type { editor } from "monaco-editor";
import { MonacoCelEditor } from "@/shared/ui/MonacoCELEditor";
import { IoSearchOutline } from "react-icons/io5";
import { TrashIcon, XMarkIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";

interface CelInputProps {
  id?: string;
  staticPositionForSuggestions?: boolean;
  value?: string;
  fieldsForSuggestions?: string[];
  onValueChange?: (value: string) => void;
  onClearValue?: () => void;
  onKeyDown?: (e: KeyboardEvent) => void;
  onFocus?: () => void;
  onIsValidChange?: (isValid: boolean) => void;
  placeholder?: string;
  disabled?: boolean;
  readOnly?: boolean;
}

const CelInput: FC<CelInputProps> = ({
  id,
  staticPositionForSuggestions,
  value = "",
  fieldsForSuggestions = [],
  onValueChange,
  onIsValidChange,
  onClearValue,
  onKeyDown,
  onFocus,
  placeholder = "Enter value",
  readOnly = false,
  disabled = false,
}) => {
  return (
    <div
      className={clsx(
        { "pl-2": readOnly, "pl-9": !readOnly },
        "flex-1 h-9 border rounded-md relative bg-white"
      )}
    >
      <MonacoCelEditor
        editorId={id}
        className={`h-20 relative ${
          staticPositionForSuggestions ? "suggestions-static-position" : ""
        }`}
        value={value}
        readOnly={readOnly}
        fieldsForSuggestions={fieldsForSuggestions}
        onValueChange={onValueChange || ((value: string) => {})}
        onIsValidChange={onIsValidChange}
        onKeyDown={onKeyDown}
        onFocus={onFocus}
      />
      {!readOnly && (
        <IoSearchOutline className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
      )}

      {placeholder && !value && (
        <div className="pointer-events-none absolute top-0 w-full h-full flex items-center text-sm text-gray-900 text-opacity-50 truncate">
          {placeholder}
        </div>
      )}
      {!readOnly && value && (
        <button
          onClick={onClearValue}
          className="absolute top-0 right-0 w-9 h-full flex items-center justify-center text-gray-400 hover:text-gray-600" // Position to the left of the Enter to apply badge
        >
          <XMarkIcon className="h-4 w-4" />
        </button>
      )}
    </div>
  );
};

export default CelInput;
