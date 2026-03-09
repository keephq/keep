import { useState } from "react";
import { Button, TextInput } from "@tremor/react";
import {
  SeverityMappingConfig,
  useSeverityMapping,
} from "@/entities/alerts/model/useSeverityMapping";
import { TrashIcon } from "@heroicons/react/24/outline";

interface MappingEntry {
  value: string;
  color: string;
}

const DEFAULT_COLOR = "#3b82f6";

export function SeverityMappingSelection({
  onClose,
}: {
  onClose?: () => void;
}) {
  const { severityMapping, setSeverityMapping } = useSeverityMapping();

  const [enabled, setEnabled] = useState(severityMapping.enabled);
  const [sourceField, setSourceField] = useState(severityMapping.sourceField);
  const [entries, setEntries] = useState<MappingEntry[]>(() => {
    const existing = Object.entries(severityMapping.mappings);
    return existing.length > 0
      ? existing.map(([value, color]) => ({ value, color }))
      : [{ value: "", color: DEFAULT_COLOR }];
  });

  const addEntry = () => {
    setEntries([...entries, { value: "", color: DEFAULT_COLOR }]);
  };

  const removeEntry = (index: number) => {
    setEntries(entries.filter((_, i) => i !== index));
  };

  const updateEntryValue = (index: number, value: string) => {
    const updated = [...entries];
    updated[index] = { ...updated[index], value };
    setEntries(updated);
  };

  const updateEntryColor = (index: number, color: string) => {
    const updated = [...entries];
    updated[index] = { ...updated[index], color };
    setEntries(updated);
  };

  const handleApply = () => {
    const mappings: Record<string, string> = {};
    for (const entry of entries) {
      if (entry.value.trim()) {
        mappings[entry.value.trim()] = entry.color;
      }
    }

    const config: SeverityMappingConfig = {
      enabled,
      sourceField: sourceField.trim(),
      mappings,
    };

    setSeverityMapping(config);
    onClose?.();
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-hidden flex flex-col">
        <span className="text-gray-400 text-sm mb-2">
          Map alert field values to custom bar colors
        </span>

        <label className="flex items-center gap-2 mb-3 cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="rounded border-gray-300"
          />
          <span className="text-sm">Enable custom severity mapping</span>
        </label>

        {enabled && (
          <>
            <div className="mb-3">
              <label className="text-sm text-gray-500 mb-1 block">
                Source field
              </label>
              <TextInput
                placeholder="e.g. priority"
                value={sourceField}
                onValueChange={setSourceField}
              />
            </div>

            <div className="flex-1 overflow-y-auto">
              <label className="text-sm text-gray-500 mb-1 block">
                Value → Color
              </label>
              <div className="space-y-2">
                {entries.map((entry, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <TextInput
                      className="flex-1"
                      placeholder="e.g. P1"
                      value={entry.value}
                      onValueChange={(v) => updateEntryValue(index, v)}
                    />
                    <input
                      type="color"
                      value={entry.color}
                      onChange={(e) => updateEntryColor(index, e.target.value)}
                      className="w-8 h-8 rounded cursor-pointer border border-gray-300 p-0.5"
                    />
                    <button
                      onClick={() => removeEntry(index)}
                      className="p-1 text-gray-400 hover:text-red-500"
                      aria-label="Remove mapping"
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>

              <Button
                variant="light"
                color="orange"
                size="xs"
                className="mt-2"
                onClick={addEntry}
              >
                + Add mapping
              </Button>
            </div>
          </>
        )}
      </div>

      <Button className="mt-4" color="orange" onClick={handleApply}>
        Apply
      </Button>
    </div>
  );
}
