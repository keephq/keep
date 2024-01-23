import { useMemo, useState } from "react";
import {
  ColumnDef,
  PaginationState,
  RowSelectionState,
} from "@tanstack/react-table";
import AlertPresets, { Option } from "./alert-presets";
import { AlertTable, columnHelper, getAlertTableColumns } from "./alert-table";
import { AlertDto, Preset } from "./models";
import AlertActions from "./alert-actions";
import { Tab } from "@headlessui/react";
import AlertTableCheckbox from "./alert-table-checkbox";
import AlertMenu from "./alert-menu";
import { useRouter } from "next/navigation";

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
  const router = useRouter();

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

  const presetAlerts = alerts
    .filter((alert) => getPresetAlerts(alert, preset))
    .sort((a, b) => b.lastReceived.getTime() - a.lastReceived.getTime());

  const alertTableColumns: ColumnDef<AlertDto>[] = useMemo(
    () => [
      ...(preset.name !== "Deleted"
        ? [
            columnHelper.display({
              id: "checkbox",
              header: (context) => (
                <AlertTableCheckbox
                  checked={context.table.getIsAllRowsSelected()}
                  indeterminate={context.table.getIsSomeRowsSelected()}
                  onChange={context.table.getToggleAllRowsSelectedHandler()}
                  disabled={alerts.length === 0}
                />
              ),
              cell: (context) => (
                <AlertTableCheckbox
                  checked={context.row.getIsSelected()}
                  indeterminate={context.row.getIsSomeSelected()}
                  onChange={context.row.getToggleSelectedHandler()}
                />
              ),
            }),
          ]
        : ([] as ColumnDef<AlertDto>[])),
      ...(getAlertTableColumns() as ColumnDef<AlertDto>[]),
      columnHelper.display({
        id: "alertMenu",
        meta: {
          thClassName: "sticky right-0",
          tdClassName: "sticky right-0",
        },
        cell: (context) => (
          <AlertMenu
            alert={context.row.original}
            openHistory={() =>
              router.replace(`/alerts?id=${context.row.original.id}`, {
                scroll: false,
              })
            }
          />
        ),
      }) as ColumnDef<AlertDto>,
    ],
    [alerts.length, router, preset.name]
  );

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
        columns={alertTableColumns}
        isAsyncLoading={isAsyncLoading}
        rowSelection={{ state: rowSelection, onChange: setRowSelection }}
        rowPagination={{
          state: rowPagination,
          onChange: setRowPagination,
        }}
        presetName={preset.name}
      />
    </Tab.Panel>
  );
}
