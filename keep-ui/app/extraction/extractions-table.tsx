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
import {
  DisplayColumnDef,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { MdRemoveCircle, MdModeEdit } from "react-icons/md";
import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { useMappings } from "utils/hooks/useMappingRules";
import { toast } from "react-toastify";
import { ExtractionRule } from "./model";
import { QuestionMarkCircleIcon } from "@heroicons/react/24/outline";
import { IoCheckmark } from "react-icons/io5";
import { HiMiniXMark } from "react-icons/hi2";

const columnHelper = createColumnHelper<ExtractionRule>();

export function extractNamedGroups(regex: string): string[] {
  const namedGroupPattern = /\(\?P<([a-zA-Z0-9]+)>[^)]*\)/g;
  let match;
  const groupNames = [];

  while ((match = namedGroupPattern.exec(regex)) !== null) {
    groupNames.push(match[1]);
  }

  return groupNames;
}

interface Props {
  extractions: ExtractionRule[];
  editCallback: (rule: ExtractionRule) => void;
}

export default function RulesTable({
  extractions: mappings,
  editCallback,
}: Props) {
  const { data: session } = useSession();
  const { mutate } = useMappings();

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
            onClick={() => deleteExtraction(context.row.original.id!)}
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
      id: "description",
      header: "Description",
      cell: (context) => context.row.original.description,
    }),
    columnHelper.display({
      id: "pre",
      header: "Pre-formatting",
      cell: (context) => (
        <div className="flex justify-center">
          {context.row.original.pre ? (
            <Icon icon={IoCheckmark} size="md" color="orange" />
          ) : (
            <Icon icon={HiMiniXMark} size="md" color="orange" />
          )}
        </div>
      ),
    }),
    columnHelper.display({
      id: "attribute",
      header: "Attribute",
      cell: (context) => context.row.original.attribute,
    }),
    columnHelper.display({
      id: "regex",
      header: () => (
        <div className="flex items-center">
          Regex{" "}
          <a
            href="https://docs.python.org/3.11/library/re.html#match-objects"
            target="_blank"
          >
            <Icon
              icon={QuestionMarkCircleIcon}
              variant="simple"
              color="gray"
              size="sm"
              tooltip="Python regex pattern for group matching"
            />
          </a>
        </div>
      ),
      cell: (context) => context.row.original.regex,
    }),
    columnHelper.display({
      id: "conditon",
      header: () => (
        <div className="flex items-center">
          Condition{" "}
          <a href="https://docs.keephq.dev/overview/presets" target="_blank">
            <Icon
              icon={QuestionMarkCircleIcon}
              variant="simple"
              color="gray"
              size="sm"
              tooltip="CEL based condition"
            />
          </a>
        </div>
      ),
      cell: (context) => context.row.original.condition,
    }),
    columnHelper.display({
      id: "newAttributes",
      header: "Extracted Attributes",
      cell: (context) => (
        <div className="flex flex-wrap">
          {extractNamedGroups(context.row.original.regex).map((attr) => (
            <Badge key={attr} color="orange" size="xs">
              {attr}
            </Badge>
          ))}
        </div>
      ),
    }),
  ] as DisplayColumnDef<ExtractionRule>[];

  const table = useReactTable({
    columns,
    data: mappings.sort((a, b) => b.priority - a.priority),
    getCoreRowModel: getCoreRowModel(),
  });

  const deleteExtraction = (extractionId: number) => {
    const apiUrl = getApiURL();
    if (confirm("Are you sure you want to delete this rule?")) {
      fetch(`${apiUrl}/extraction/${extractionId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      }).then((response) => {
        if (response.ok) {
          mutate();
          toast.success("Extraction deleted successfully");
        } else {
          toast.error(
            "Failed to delete extraction rule, contact us if this persists"
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
