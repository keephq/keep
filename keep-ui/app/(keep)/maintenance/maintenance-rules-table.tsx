import {
  Button,
  Icon,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import {
  DisplayColumnDef,
  ExpandedState,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { MdRemoveCircle, MdModeEdit } from "react-icons/md";
import { toast } from "react-toastify";
import { MaintenanceRule } from "./model";
import { IoCheckmark } from "react-icons/io5";
import { HiMiniXMark } from "react-icons/hi2";
import { useState } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { useI18n } from "@/i18n/hooks/useI18n";

const columnHelper = createColumnHelper<MaintenanceRule>();

interface Props {
  maintenanceRules: MaintenanceRule[];
  editCallback: (rule: MaintenanceRule) => void;
}

export default function MaintenanceRulesTable({
  maintenanceRules,
  editCallback,
}: Props) {
  const api = useApi();
  const { t } = useI18n();

  const [expanded, setExpanded] = useState<ExpandedState>({});

  const columns = [
    columnHelper.display({
      id: "delete",
      header: "",
      cell: (context) => (
        <div className={"space-x-1 flex flex-row items-center justify-center"}>
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            icon={MdModeEdit}
            onClick={(e: any) => {
              e.preventDefault();
              editCallback(context.row.original!);
            }}
          />
          <Button
            color="red"
            size="xs"
            variant="secondary"
            icon={MdRemoveCircle}
            onClick={(e: any) => {
              e.preventDefault();
              deleteMaintenanceRule(context.row.original.id!);
            }}
          />
        </div>
      ),
    }),
    columnHelper.display({
      id: "name",
      header: t("maintenance.table.name"),
      cell: ({ row }) => row.original.name,
    }),
    columnHelper.display({
      id: "description",
      header: t("maintenance.table.description"),
      cell: (context) => context.row.original.description,
    }),
    columnHelper.display({
      id: "start_time",
      header: t("maintenance.table.startTime"),
      cell: (context) =>
        new Date(context.row.original.start_time + "Z").toLocaleString(),
    }),
    columnHelper.display({
      id: "CEL",
      header: t("maintenance.table.cel"),
      cell: (context) => context.row.original.cel_query,
    }),
    columnHelper.display({
      id: "end_time",
      header: t("maintenance.table.endTime"),
      cell: (context) =>
        context.row.original.end_time
          ? new Date(context.row.original.end_time + "Z").toLocaleString()
          : "N/A",
    }),
    columnHelper.display({
      id: "enabled",
      header: t("maintenance.table.enabled"),
      cell: (context) => (
        <div>
          {context.row.original.enabled ? (
            <Icon icon={IoCheckmark} size="md" color="orange" />
          ) : (
            <Icon icon={HiMiniXMark} size="md" color="orange" />
          )}
        </div>
      ),
    }),
  ] as DisplayColumnDef<MaintenanceRule>[];

  const table = useReactTable({
    getRowId: (row) => row.id.toString(),
    columns,
    data: maintenanceRules,
    state: { expanded },
    getCoreRowModel: getCoreRowModel(),
    onExpandedChange: setExpanded,
  });

  const deleteMaintenanceRule = (maintenanceRuleId: number) => {
    if (confirm(t("maintenance.messages.confirmDelete"))) {
      api
        .delete(`/maintenance/${maintenanceRuleId}`)
        .then(() => {
          toast.success(t("maintenance.messages.deleteSuccess"));
        })
        .catch((error: any) => {
          showErrorToast(error, t("maintenance.messages.deleteFailed"));
        });
    }
  };

  return (
    <Table>
      <TableHead>
        {table.getHeaderGroups().map((headerGroup) => (
          <TableRow
            className="border-b border-tremor-border dark:border-dark-tremor-border"
            key={headerGroup.id}
          >
            {headerGroup.headers.map((header) => (
              <TableHeaderCell
                className="text-tremor-content-strong dark:text-dark-tremor-content-strong"
                key={header.id}
              >
                {flexRender(
                  header.column.columnDef.header,
                  header.getContext()
                )}
              </TableHeaderCell>
            ))}
          </TableRow>
        ))}
      </TableHead>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <>
            <TableRow
              className="even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted hover:bg-slate-100"
              key={row.id}
              onClick={() => row.toggleExpanded()}
            >
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
            {row.getIsExpanded() && (
              <TableRow className="pl-2.5">
                <TableCell colSpan={columns.length}>
                  <div className="flex space-x-2 divide-x">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold">{t("maintenance.table.createdBy")}:</span>
                      <span>{row.original.created_by}</span>
                    </div>
                    {row.original.updated_at && (
                      <>
                        <div className="flex items-center space-x-2 pl-2.5">
                          <span className="font-bold">{t("maintenance.table.updatedAt")}:</span>
                          <span>
                            {new Date(
                              row.original.updated_at + "Z"
                            ).toLocaleString()}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2 pl-2.5">
                          <span className="font-bold">{t("maintenance.table.enabled")}:</span>
                          <span>{row.original.enabled ? t("common.labels.yes") : t("common.labels.no")}</span>
                        </div>
                      </>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            )}
          </>
        ))}
      </TableBody>
    </Table>
  );
}
