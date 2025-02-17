import { Text, TextInputProps } from "@tremor/react";
import { Textarea, TextInput } from "@/components/ui";
import React from "react";

export function EditorField({ name, value, ...rest }: TextInputProps) {
  if (name === "code") {
    return (
      <div>
        <Text className="capitalize mb-1.5">{name}</Text>
        {/* FIX: type */}
        {/* @ts-ignore */}
        <Textarea
          id={name}
          placeholder={name}
          className="mb-2.5 min-h-[100px] text-xs font-mono"
          value={value || ""}
          {...rest}
        />
      </div>
    );
  }
  return (
    <div>
      <Text className="capitalize mb-1.5">{name}</Text>
      <TextInput
        id={name}
        placeholder={name}
        className="mb-2.5"
        value={value || ""}
        {...rest}
      />
    </div>
  );
}
