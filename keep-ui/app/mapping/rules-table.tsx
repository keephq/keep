import {
  Badge,
  Button,
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
} from "@tanstack/react-table";
import { MdRemoveCircle } from "react-icons/md";
import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { useMappings } from "utils/hooks/useMappingRules";
import { toast } from "react-toastify";

const columnHelper = createColumnHelper<MappingRule>();

export default function RulesTable({ mappings, editCallback }: { mappings: MappingRule[]; editCallback: (rule: MappingRule) => void }) {
  const { data: session } = useSession();
  const { mutate } = useMappings();

  const columns = [
    columnHelper.display({
      id: "id",
      header: "#",
      cell: (context) => context.row.original.id,
    }),
    columnHelper.display({
      id: "priority",
      header: "Priority",
      cell: (context) => context.row.original.priority,
    }),
    columnHelper.display({
      id: "name",
      header: "Name",
      cell: (context) => context.row.original.name,
    }),
    columnHelper.display({
      id: "description",
      header: "Description",
      cell: (context) => context.row.original.description,
    }),
    columnHelper.display({
      id: "fileName",
      header: "Original File Name",
      cell: (context) => context.row.original.file_name,
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
      id: "delete",
      header: "",
      cell: (context) => (
        <div className={"space-x-4 flex flex-row items-center justify-center"}>
          <Button
            color="red"
            size="xs"
            variant="secondary"
            icon={MdRemoveCircle}
            onClick={() => deleteRule(context.row.original.id!)}
          />
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            onClick={() => editCallback(context.row.original!)}
          > Edit </Button>
        </div>
      ),
    }),
  ] as DisplayColumnDef<MappingRule>[];

  const table = useReactTable({
    columns,
    data: mappings.sort((a, b) => b.priority - a.priority),
    getCoreRowModel: getCoreRowModel(),
  });

  const deleteRule = (ruleId: number) => {
    const apiUrl = getApiURL();
    if (confirm("Are you sure you want to delete this rule?")) {
      fetch(`${apiUrl}/mapping/${ruleId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      }).then((response) => {
        if (response.ok) {
          mutate();
          toast.success("Rule deleted successfully");
        } else {
          toast.error("Failed to delete rule, contact us if this persists");
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
            {headerGroup.headers.map((header) => {
              return (
                <TableHeaderCell
                  className="text-tremor-content-strong dark:text-dark-tremor-content-strong"
                  key={header.id}
                >
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext()
                  )}
                </TableHeaderCell>
              );
            })}
          </TableRow>
        ))}
      </TableHead>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <TableRow
            className="even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted hover:bg-slate-100"
            key={row.id}
          >
            {row.getVisibleCells().map((cell) => (
              <TableCell key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
