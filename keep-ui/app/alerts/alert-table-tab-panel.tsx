import { useMemo, useState } from "react";
import { RowSelectionState } from "@tanstack/react-table";
import AlertPresets, { Option } from "./alert-presets";
import { AlertTable } from "./alert-table";
import { AlertDto, Preset } from "./models";
import AlertActions from "./alert-actions";
import { Tab } from "@headlessui/react";

const getPresetAlerts = (alert: AlertDto, preset: Preset): boolean => {
  if (preset.options.length === 0) {
    return true;
  }

  if (preset.name === "Deleted") {
    return alert.deleted.includes(alert.lastReceived.toISOString());
  }

  return preset.options.every((option) => {
    const [key, value] = option.value.split("=");

    if (key && value) {
      const lowercaseKey = key.toLowerCase() as keyof AlertDto;
      const lowercaseValue = value.toLowerCase();

      const alertValue = alert[lowercaseKey];

      if (Array.isArray(alertValue)) {
        return alertValue.every((v) => lowercaseValue.split(",").includes(v));
      }

      if (typeof alertValue === "string") {
        return alertValue.toLowerCase().includes(lowercaseValue);
      }
    }

    return false;
  });
};

interface Props {
  alerts: AlertDto[];
  preset: Preset;
  isAsyncLoading: boolean;
}

export default function AlertTableTabPanel({
  alerts,
  preset,
  isAsyncLoading,
}: Props) {
  const [selectedOptions, setSelectedOptions] = useState<Option[]>(
    preset.options
  );

  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const selectedRowIds = Object.entries(rowSelection).reduce<string[]>(
    (acc, [alertId, isSelected]) => {
      if (isSelected) {
        return acc.concat(alertId);
      }
      return acc;
    },
    []
  );

  const presetAlerts = alerts
    .filter((alert) => getPresetAlerts(alert, preset))
    .sort((a, b) => b.lastReceived.getTime() - a.lastReceived.getTime());

  return (
    <Tab.Panel className="mt-4">
      {selectedRowIds.length ? (
        <AlertActions selectedRowIds={selectedRowIds} alerts={presetAlerts} />
      ) : (
        <AlertPresets
          preset={preset}
          alerts={presetAlerts}
          selectedOptions={selectedOptions}
          setSelectedOptions={setSelectedOptions}
          isLoading={isAsyncLoading}
        />
      )}
      <AlertTable
        alerts={presetAlerts}
        isAsyncLoading={isAsyncLoading}
        rowSelection={
          preset.name !== "Deleted"
            ? { state: rowSelection, onChange: setRowSelection }
            : undefined
        }
        presetName={preset.name}
      />
    </Tab.Panel>
  );
}
