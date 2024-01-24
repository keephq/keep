import { useState } from "react";
import { PaginationState, RowSelectionState } from "@tanstack/react-table";
import AlertPresets, { Option } from "./alert-presets";
import { AlertTable, useAlertTableCols } from "./alert-table";
import { AlertDto, AlertKnownKeys, Preset } from "./models";
import AlertActions from "./alert-actions";
import { TabPanel } from "@tremor/react";

const getPresetAlerts = (
  alert: AlertDto,
  options: Option[],
  presetName: string
): boolean => {
  // Conditional filtering based on selectedPreset.name
  if (presetName === "Deleted") {
    return alert.deleted === true;
  }
  if (presetName === "Groups") {
    return alert.group === true;
  }

  if (options.length === 0) {
    return true;
  }

  return options.every((option) => {
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

  const [rowPagination, setRowPagination] = useState<PaginationState>({
    pageSize: 10,
    pageIndex: 0,
  });

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

  const sortedPresetAlerts = alerts
    .filter((alert) => getPresetAlerts(alert, selectedOptions, preset.name))
    .sort((a, b) => b.lastReceived.getTime() - a.lastReceived.getTime());

  const additionalColsToGenerate = [
    ...new Set(
      alerts
        .flatMap((alert) => Object.keys(alert))
        .filter((key) => AlertKnownKeys.includes(key) === false)
    ),
  ];

  const alertTableColumns = useAlertTableCols({
    additionalColsToGenerate: additionalColsToGenerate,
    isCheckboxDisplayed: preset.name !== "Deleted",
    isMenuDisplayed: true,
  });

  return (
    <TabPanel className="mt-4">
      {selectedRowIds.length ? (
        <AlertActions
          selectedRowIds={selectedRowIds}
          alerts={sortedPresetAlerts}
        />
      ) : (
        <AlertPresets
          preset={preset}
          alerts={sortedPresetAlerts}
          selectedOptions={selectedOptions}
          setSelectedOptions={setSelectedOptions}
          isLoading={isAsyncLoading}
        />
      )}
      <AlertTable
        alerts={sortedPresetAlerts}
        columns={alertTableColumns}
        isAsyncLoading={isAsyncLoading}
        rowSelection={{ state: rowSelection, onChange: setRowSelection }}
        rowPagination={{
          state: rowPagination,
          onChange: setRowPagination,
        }}
        presetName={preset.name}
      />
    </TabPanel>
  );
}
