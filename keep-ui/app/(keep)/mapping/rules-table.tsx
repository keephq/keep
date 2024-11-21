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
  ExpandedState,
} from "@tanstack/react-table";
import { MdRemoveCircle, MdModeEdit } from "react-icons/md";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useApiUrl } from "utils/hooks/useConfig";
import { useMappings } from "utils/hooks/useMappingRules";
import { toast } from "react-toastify";
import { useState } from "react";

const columnHelper = createColumnHelper<MappingRule>();

interface Props {
  mappings: MappingRule[];
  editCallback: (rule: MappingRule) => void;
}

export default function RulesTable({ mappings, editCallback }: Props) {
  const { data: session } = useSession();
  const { mutate } = useMappings();
  const apiUrl = useApiUrl();
  const [expanded, setExpanded] = useState<ExpandedState>({});

  const columns = [
    columnHelper.display({
      id: "delete",
      header: "",
      cell: (context) => (
        <div className={"space-x-1 flex flex-row items-center justify-center"}>
          {/*If user wants to edit the mapping. We use the callback to set the data in mapping.tsx which is then passed to the create-new-mapping.tsx form*/}
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            icon={MdModeEdit}
            onClick={() => editCallback(context.row.original!)}
          />
          <Button
            color="red"
            size="xs"
            variant="secondary"
            icon={MdRemoveCircle}
            onClick={() => deleteRule(context.row.original.id!)}
          />
        </div>
      ),
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
      id: "type",
      header: "Type",
      cell: (context) => context.row.original.type,
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
                      <span className="font-bold">Created At:</span>
                      <span>
                        {new Date(
                          row.original.created_at + "Z"
                        ).toLocaleString()}
                      </span>
                    </div>
                    <div className="flex items-center space-x-2 pl-2.5">
                      <span className="font-bold">Created By:</span>
                      <span>{row.original.created_by}</span>
                    </div>
                    {row.original.last_updated_at && (
                      <>
                        <div className="flex items-center space-x-2 pl-2.5">
                          <span className="font-bold">Updated At:</span>
                          <span>
                            {new Date(
                              row.original.last_updated_at + "Z"
                            ).toLocaleString()}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2 pl-2.5">
                          <span className="font-bold">Updated By:</span>
                          <span>{row.original.updated_by}</span>
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
