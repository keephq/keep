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
} from "@tanstack/react-table";
import { MdRemoveCircle, MdModeEdit, MdPlayArrow } from "react-icons/md";
import { useMappings } from "utils/hooks/useMappingRules";
import { toast } from "react-toastify";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { FaFileCsv, FaFileCode, FaNetworkWired } from "react-icons/fa";
import { Fragment, useState } from "react";
import { useRouter } from "next/navigation";
import RunMappingModal from "./run-mapping-modal";
import { TrashIcon } from "@heroicons/react/24/outline";
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
  const router = useRouter();
  const [runModalRule, setRunModalRule] = useState<number | null>(null);

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
        <div className="flex flex-wrap gap-1">
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
            icon={MdPlayArrow}
            tooltip="Run"
            onClick={(event) => {
              event.stopPropagation();
              setRunModalRule(context.row.original.id!);
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
            icon={TrashIcon}
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
    getRowId: (row) => row.id.toString(),
    columns,
    data: mappings.sort((a, b) => b.priority - a.priority),
    getCoreRowModel: getCoreRowModel(),
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
    <>
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
            <TableRow
              className="hover:bg-slate-100 group cursor-pointer"
              key={row.id}
              onClick={() =>
                router.push(`/mapping/${row.original.id}/executions`)
              }
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
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <RunMappingModal
        ruleId={runModalRule!}
        isOpen={runModalRule !== null}
        onClose={() => setRunModalRule(null)}
      />
    </>
  );
}
