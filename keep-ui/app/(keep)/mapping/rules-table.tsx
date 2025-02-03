import {
  Badge,
  Button,
  Icon,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import { MappingRule } from "./models";
import {
  DisplayColumnDef,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
  ExpandedState,
} from "@tanstack/react-table";
import { MdRemoveCircle, MdModeEdit } from "react-icons/md";
import { useMappings } from "utils/hooks/useMappingRules";
import { toast } from "react-toastify";
import { useState } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import * as HoverCard from "@radix-ui/react-hover-card";
import TimeAgo from "react-timeago";
import { FaFileCsv, FaFileCode, FaNetworkWired } from "react-icons/fa";

const columnHelper = createColumnHelper<MappingRule>();

interface Props {
  mappings: MappingRule[];
  editCallback: (rule: MappingRule) => void;
}

const getTypeIcon = (type: string) => {
  switch (type) {
    case "csv":
      return <Icon icon={FaFileCsv} tooltip="CSV" className="text-green-500" />;
    case "json":
      return (
        <Icon icon={FaFileCode} tooltip="JSON" className="text-blue-500" />
      );
    case "topology":
      return (
        <Icon
          icon={FaNetworkWired}
          tooltip="Topology"
          className="text-purple-500"
        />
      );
    default:
      return null;
  }
};

export default function RulesTable({ mappings, editCallback }: Props) {
  const api = useApi();
  const { mutate } = useMappings();
  const [expanded, setExpanded] = useState<ExpandedState>({});

  const columns = [
    columnHelper.accessor("name", {
      header: "Name",
      cell: (info) => info.getValue(),
    }),
    columnHelper.accessor("description", {
      header: "Description",
      cell: (info) => info.getValue(),
    }),
    columnHelper.display({
      id: "priority",
      header: "Priority",
      cell: (context) => context.row.original.priority,
    }),
    columnHelper.display({
      id: "type",
      header: "Type",
      cell: (context) => getTypeIcon(context.row.original.type),
    }),
    columnHelper.display({
      id: "matchers",
      header: "Matchers",
      cell: (context) => context.row.original.matchers.join(","),
    }),
    columnHelper.display({
      id: "attributes",
      header: "Attributes",
      cell: (context) => (
        <div className="flex flex-wrap">
          {context.row.original.attributes?.map((attr) => (
            <Badge key={attr} color="orange" size="xs">
              {attr}
            </Badge>
          ))}
        </div>
      ),
    }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: (context) => (
        <div className="space-x-1 flex flex-row items-center justify-end opacity-0 group-hover:opacity-100 border-l">
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            icon={MdModeEdit}
            tooltip="Edit"
            onClick={(event) => {
              event.stopPropagation();
              editCallback(context.row.original!);
            }}
          />
          <Button
            color="red"
            size="xs"
            variant="secondary"
            icon={MdRemoveCircle}
            tooltip="Delete"
            onClick={(event) => {
              event.stopPropagation();
              deleteRule(context.row.original.id!);
            }}
          />
        </div>
      ),
      meta: {
        sticky: true,
      },
    }),
  ] as DisplayColumnDef<MappingRule>[];

  const table = useReactTable({
    columns,
    data: mappings.sort((a, b) => b.priority - a.priority),
    state: { expanded },
    getCoreRowModel: getCoreRowModel(),
    onExpandedChange: setExpanded,
  });

  const deleteRule = (ruleId: number) => {
    if (confirm("Are you sure you want to delete this rule?")) {
      api
        .delete(`/mapping/${ruleId}`)
        .then(() => {
          mutate();
          toast.success("Rule deleted successfully");
        })
        .catch((error: any) => {
          showErrorToast(error, "Failed to delete rule");
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
                className={`text-tremor-content-strong dark:text-dark-tremor-content-strong ${
                  header.column.columnDef.meta?.sticky
                    ? "sticky right-0 bg-white dark:bg-gray-800"
                    : ""
                }`}
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
            <HoverCard.Root openDelay={2000} closeDelay={1000}>
              <HoverCard.Trigger asChild className="hover:cursor-pointer">
                <TableRow
                  className="even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted hover:bg-slate-100 group"
                  key={row.id}
                  onClick={() => row.toggleExpanded()}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      className={`${
                        cell.column.columnDef.meta?.sticky
                          ? "sticky right-0 bg-white dark:bg-gray-800"
                          : ""
                      }`}
                      key={cell.id}
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              </HoverCard.Trigger>
              <HoverCard.Portal>
                <HoverCard.Content
                  side="left"
                  className="rounded-tremor-default border border-tremor-border bg-tremor-background p-4 shadow-lg z-[9999] overflow-y-scroll"
                  sideOffset={5}
                >
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Created:
                      </span>
                      <span className="whitespace-nowrap text-sm text-gray-900">
                        <TimeAgo
                          date={new Date(
                            row.original.created_at + "Z"
                          ).toLocaleString()}
                        />
                      </span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Created by:
                      </span>
                      <span className="whitespace-nowrap text-sm text-gray-900">
                        {row.original.created_by}
                      </span>
                    </div>
                    {row.original.last_updated_at && (
                      <>
                        <div className="flex items-center space-x-2">
                          <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Last update:
                          </span>
                          <span className="whitespace-nowrap text-sm text-gray-900">
                            <TimeAgo
                              date={new Date(
                                row.original.last_updated_at + "Z"
                              ).toLocaleString()}
                            />
                          </span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Updated by:
                          </span>
                          <span className="whitespace-nowrap text-sm text-gray-900">
                            {row.original.updated_by}
                          </span>
                        </div>
                        {row.original.file_name && (
                          <div className="flex items-center space-x-2">
                            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                              File Name:
                            </span>
                            <span className="whitespace-nowrap text-sm text-gray-900">
                              {row.original.file_name}
                            </span>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  <HoverCard.Arrow className="fill-tremor-border" />
                </HoverCard.Content>
              </HoverCard.Portal>
            </HoverCard.Root>
            {row.getIsExpanded() && row.original.type === "csv" && (
              <TableRow className="pl-2.5">
                <TableCell colSpan={columns.length}>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead>
                        <tr>
                          {Object.keys(row.original.rows[0] || {}).map(
                            (key) => (
                              <th
                                key={key}
                                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                              >
                                {key}
                              </th>
                            )
                          )}
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {row.original.rows.map((csvRow, index) => (
                          <tr key={index}>
                            {Object.values(csvRow).map((value, idx) => (
                              <td
                                key={idx}
                                className="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
                              >
                                {value}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
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
