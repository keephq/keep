import { useState } from "react";
import { PaginationState, RowSelectionState } from "@tanstack/react-table";
import AlertPresets, { Option } from "./alert-presets";
import { AlertTable } from "./alert-table";
import { useAlertTableCols } from "./alert-table-utils";
import { AlertDto, AlertKnownKeys, Preset } from "./models";
import AlertActions from "./alert-actions";
import { TabPanel } from "@tremor/react";

const getPresetAlerts = (alert: AlertDto, presetName: string): boolean => {
  if (presetName === "Deleted") {
    return alert.deleted === true;
  }

  if (presetName === "Groups") {
    return alert.group === true;
  }

  if (presetName === "Feed") {
    return alert.deleted === false;
  }

  return true;
};

const getOptionAlerts = (alert: AlertDto, options: Option[]): boolean =>
  options.length > 0
    ? options.some((option) => {
        const [key, value] = option.value.split("=");

        if (key && value) {
          const attribute = key.toLowerCase() as keyof AlertDto;
          const lowercaseAttributeValue = value.toLowerCase();

          const alertAttributeValue = alert[attribute];

          if (Array.isArray(alertAttributeValue)) {
            return alertAttributeValue.every((v) =>
              lowercaseAttributeValue.split(",").includes(v)
            );
          }

          if (typeof alertAttributeValue === "string") {
            return alertAttributeValue
              .toLowerCase()
              .includes(lowercaseAttributeValue);
          }
        }

        return true;
      })
    : true;

const getPresetAndOptionsAlerts = (
  alert: AlertDto,
  options: Option[],
  presetName: string
) => getPresetAlerts(alert, presetName) && getOptionAlerts(alert, options);

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
    .filter((alert) =>
      getPresetAndOptionsAlerts(alert, selectedOptions, preset.name)
    )
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
