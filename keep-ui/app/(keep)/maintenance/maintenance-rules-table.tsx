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
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { toast } from "react-toastify";
import { useApiUrl, useConfig } from "utils/hooks/useConfig";
import { MaintenanceRule } from "./model";
import { IoCheckmark } from "react-icons/io5";
import { HiMiniXMark } from "react-icons/hi2";
import { useState } from "react";
import { ReadOnlyAwareToaster } from "@/shared/lib/ReadOnlyAwareToaster";

const columnHelper = createColumnHelper<MaintenanceRule>();

interface Props {
  maintenanceRules: MaintenanceRule[];
  editCallback: (rule: MaintenanceRule) => void;
}

export default function MaintenanceRulesTable({
  maintenanceRules,
  editCallback,
}: Props) {
  const { data: session } = useSession();
  const { data: configData } = useConfig();
  const apiUrl = useApiUrl();

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
      header: "Name",
      cell: ({ row }) => row.original.name,
    }),
    columnHelper.display({
      id: "description",
      header: "Description",
      cell: (context) => context.row.original.description,
    }),
    columnHelper.display({
      id: "start_time",
      header: "Start Time",
      cell: (context) =>
        new Date(context.row.original.start_time).toLocaleString(),
    }),
    columnHelper.display({
      id: "CEL",
      header: "CEL",
      cell: (context) => context.row.original.cel_query,
    }),
    columnHelper.display({
      id: "end_time",
      header: "End Time",
      cell: (context) =>
        context.row.original.end_time
          ? new Date(context.row.original.end_time).toLocaleString()
          : "N/A",
    }),
    columnHelper.display({
      id: "enabled",
      header: "Enabled",
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
    columns,
    data: maintenanceRules,
    state: { expanded },
    getCoreRowModel: getCoreRowModel(),
    onExpandedChange: setExpanded,
  });

  const deleteMaintenanceRule = (maintenanceRuleId: number) => {
    if (confirm("Are you sure you want to delete this maintenance rule?")) {
      fetch(`${apiUrl}/maintenance/${maintenanceRuleId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      }).then((response) => {
        if (response.ok) {
          toast.success("Maintenance rule deleted successfully");
        } else {
          ReadOnlyAwareToaster.error(
            "Failed to delete maintenance rule, contact us if this persists",
            configData
          );
        }
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
                      <span className="font-bold">Created By:</span>
                      <span>{row.original.created_by}</span>
                    </div>
                    {row.original.updated_at && (
                      <>
                        <div className="flex items-center space-x-2 pl-2.5">
                          <span className="font-bold">Updated At:</span>
                          <span>
                            {new Date(
                              row.original.updated_at + "Z"
                            ).toLocaleString()}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2 pl-2.5">
                          <span className="font-bold">Enabled:</span>
                          <span>{row.original.enabled ? "Yes" : "No"}</span>
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
