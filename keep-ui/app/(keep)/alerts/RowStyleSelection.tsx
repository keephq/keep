import React from "react";
import { Text } from "@tremor/react";
import {
  RowStyle,
  useAlertRowStyle,
} from "@/entities/alerts/model/useAlertRowStyle";
interface RowStyleSelectionProps {
  onClose?: () => void;
}

export function RowStyleSelection({ onClose }: RowStyleSelectionProps) {
  const [rowStyle, setRowStyle] = useAlertRowStyle();

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
            <Text>Compact</Text>
            <Text className="text-sm text-gray-500">
              Compact rows to show more data
            </Text>
          </button>
          <button
            type="button"
            onClick={() => handleStyleChange("relaxed")}
            className={`w-full text-left p-3 rounded ${
              rowStyle === "relaxed"
                ? "bg-orange-100 text-orange-700"
                : "hover:bg-gray-100"
            }`}
          >
            <Text>Relaxed</Text>
            <Text className="text-sm text-gray-500">
              Standard row height with comfortable spacing
            </Text>
          </button>
        </div>
      </div>
    </form>
  );
}
