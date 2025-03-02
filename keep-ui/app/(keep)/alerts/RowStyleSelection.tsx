import React from "react";
import { Button, Text } from "@tremor/react";
import { useLocalStorage } from "utils/hooks/useLocalStorage";

interface RowStyleSelectionProps {
  onClose?: () => void;
}

export type RowStyle = "default" | "dense";

export function RowStyleSelection({ onClose }: RowStyleSelectionProps) {
  const [rowStyle, setRowStyle] = useLocalStorage<RowStyle>(
    "alert-table-row-style",
    "default"
  );

  const handleStyleChange = (style: RowStyle) => {
    setRowStyle(style);
    onClose?.();
  };

  return (
    <form className="flex flex-col h-full">
      <div className="flex-1 overflow-hidden flex flex-col">
        <span className="text-gray-400 text-sm mb-2">Set row density</span>
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => handleStyleChange("default")}
            className={`w-full text-left p-3 rounded ${
              rowStyle === "default"
                ? "bg-orange-100 text-orange-700"
                : "hover:bg-gray-100"
            }`}
          >
            <Text>Default</Text>
            <Text className="text-sm text-gray-500">
              Standard row height with comfortable spacing
            </Text>
          </button>
          <button
            type="button"
            onClick={() => handleStyleChange("dense")}
            className={`w-full text-left p-3 rounded ${
              rowStyle === "dense"
                ? "bg-orange-100 text-orange-700"
                : "hover:bg-gray-100"
            }`}
          >
            <Text>Dense</Text>
            <Text className="text-sm text-gray-500">
              Compact rows to show more data
            </Text>
          </button>
        </div>
      </div>
    </form>
  );
}
