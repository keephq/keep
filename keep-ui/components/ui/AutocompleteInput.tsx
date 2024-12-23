"use client";

import React, { useState, useEffect, useRef } from "react";
import { TextInput } from "./TextInput";
import { cn } from "utils/helpers";

export type Option<T> = {
  label: string;
  value: T;
};

export type AutocompleteInputProps<T> = {
  options: Option<T>[];
  onSelect: (option: Option<T>) => void;
  getId: (option: Option<T>) => string;
  placeholder: string;
  wrapperClassName?: string;
} & Omit<React.ComponentProps<typeof TextInput>, "onSelect">;

export function AutocompleteInput<T>({
  options,
  onSelect,
  getId,
  placeholder,
  wrapperClassName,
  ...props
}: AutocompleteInputProps<T>) {
  const [inputValue, setInputValue] = useState("");
  const [filteredOptions, setFilteredOptions] = useState<Option<T>[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLUListElement | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInputValue(value);
    setIsOpen(true);

    const filtered = options.filter((option) =>
      option.label.toLowerCase().includes(value.toLowerCase())
    );
    setFilteredOptions(filtered);
    setFocusedIndex(-1);
  };

  const clearInput = () => {
    setInputValue("");
    setIsOpen(false);
  };

  const handleOptionClick = (option: Option<T>) => {
    setInputValue(option.label);
    setIsOpen(false);
    onSelect(option);
    clearInput();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusedIndex((prevIndex) =>
        prevIndex < filteredOptions.length - 1 ? prevIndex + 1 : prevIndex
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusedIndex((prevIndex) =>
        prevIndex > 0 ? prevIndex - 1 : prevIndex
      );
    } else if (e.key === "Enter" || (e.key === " " && focusedIndex !== -1)) {
      e.preventDefault();
      if (focusedIndex >= 0 && focusedIndex < filteredOptions.length) {
        handleOptionClick(filteredOptions[focusedIndex]);
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
      inputRef.current?.blur();
    }
  };

  useEffect(() => {
    if (isOpen && listRef.current && focusedIndex >= 0) {
      const focusedElement = listRef.current.children[
        focusedIndex
      ] as HTMLElement;
      if (focusedElement) {
        focusedElement.scrollIntoView({ block: "nearest" });
      }
    }
  }, [focusedIndex, isOpen]);

  return (
    <div ref={wrapperRef} className={cn("relative", wrapperClassName)}>
      <TextInput
        ref={inputRef}
        value={inputValue}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        aria-autocomplete="list"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-activedescendant={
          focusedIndex >= 0 ? `option-${focusedIndex}` : undefined
        }
        {...props}
      />
      {isOpen && filteredOptions.length > 0 && (
        <ul
          ref={listRef}
          className="absolute z-50 w-full bg-white border border-gray-300 mt-1 max-h-60 overflow-auto rounded-md shadow-lg"
          role="listbox"
        >
          {filteredOptions.map((option, index) => (
            <li
              key={getId(option)}
              id={`option-${getId(option)}`}
              role="option"
              aria-selected={index === focusedIndex}
              tabIndex={-1}
              onClick={() => handleOptionClick(option)}
              onMouseEnter={() => setFocusedIndex(index)}
              className={`px-4 py-2 cursor-pointer ${
                index === focusedIndex
                  ? "bg-blue-100 outline outline-2 outline-blue-500"
                  : "hover:bg-gray-100"
              }`}
            >
              {option.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
