import { Text } from "@tremor/react";
import { Textarea, TextInput } from "@/components/ui";
import React from "react";

export function EditorField({
  name,
  value,
  onChange,
}: {
  name: string;
  value: string;
  onChange: (e: any) => void;
}) {
  if (name === "code") {
    return (
      <div>
        <Text className="capitalize mb-1.5">{name}</Text>
        <Textarea
          id={`${name}`}
          placeholder={name}
          onChange={onChange}
          className="mb-2.5 min-h-[100px] text-xs font-mono"
          value={value || ""}
        />
      </div>
    );
  }
  return (
    <div>
      <Text className="capitalize mb-1.5">{name}</Text>
      <TextInput
        id={`${name}`}
        placeholder={name}
        onChange={onChange}
        className="mb-2.5"
        value={value || ""}
      />
    </div>
  );
}
