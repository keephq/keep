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
  Text,
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
import { MdRemoveCircle, MdModeEdit, MdPlayArrow } from "react-icons/md";
import { useMappings } from "utils/hooks/useMappingRules";
import { toast } from "react-toastify";
import { useState } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import * as HoverCard from "@radix-ui/react-hover-card";
import TimeAgo from "react-timeago";
import { FaFileCsv, FaFileCode, FaNetworkWired } from "react-icons/fa";
import { Fragment } from "react";
import { Cog8ToothIcon } from "@heroicons/react/24/solid";
import { useRouter } from "next/navigation";
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

const formattedMatchers = (matchers: string[][]) => {
  return (
    <div className="inline-flex items-center">
      {matchers.map((matcher, index) => (
        <Fragment key={index}>
          <div className="p-2 bg-gray-50 border rounded space-x-2">
            {matcher.map((attribute, index) => (
              <Fragment key={attribute}>
                <span className="space-x-2">
                  <b>{attribute}</b>{" "}
                  {index < matcher.length - 1 && <span>+</span>}
                </span>
              </Fragment>
            ))}
          </div>
          {index < matchers.length - 1 && (
            <Text className="mx-1" color="slate">
              OR
            </Text>
          )}
        </Fragment>
      ))}
    </div>
  );
};

export default function RulesTable({ mappings, editCallback }: Props) {
  const api = useApi();
  const { mutate } = useMappings();
  const [expanded, setExpanded] = useState<ExpandedState>({});
  const router = useRouter();

  const columns = [
    columnHelper.accessor("name", {
      header: "Name",
      cell: (context) => {
        return (
          <div className="flex items-center space-x-2">
            {getTypeIcon(context.row.original.type)} {context.row.original.name}
          </div>
        );
      },
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
      id: "matchers",
      header: "Matchers",
      cell: (context) => formattedMatchers(context.row.original.matchers),
    }),
    columnHelper.display({
      id: "attributes",
      header: "Enriched With",
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
        <div className="space-x-1 flex flex-row items-center justify-end opacity-0 group-hover:opacity-100 bg-slate-100 border-l">
          <Button
            color="orange"
            size="xs"
            icon={Cog8ToothIcon}
            tooltip="Executions"
            onClick={(event) => {
              event.stopPropagation();
              router.push(`/mapping/${context.row.original.id}/executions`);
            }}
          />
          <Button
            color="orange"
            size="xs"
            icon={MdPlayArrow}
            tooltip="Run"
            onClick={(event) => {
              event.stopPropagation();
            }}
          />
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
            <HoverCard.Root>
              <HoverCard.Trigger asChild className="hover:cursor-pointer">
                <TableRow
                  className="even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted hover:bg-slate-100 group overflow-hidden"
                  key={row.id}
                  onClick={() => row.toggleExpanded()}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      className={`${
                        cell.column.columnDef.meta?.sticky
                          ? "sticky right-0 bg-white dark:bg-gray-800 hover:bg-slate-100 group-hover:bg-slate-100"
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
                <HoverCard.Content className="rounded-tremor-default border border-tremor-border bg-tremor-background p-4 shadow-lg z-[9999] overflow-y-scroll">
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
                    {row.original.updated_by && (
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
