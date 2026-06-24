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
  createColumnHelper,
  DisplayColumnDef,
  ExpandedState,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { MdModeEdit, MdPlayArrow, MdRemoveCircle } from "react-icons/md";
import { useExtractions } from "utils/hooks/useExtractionRules";
import { toast } from "react-toastify";
import { ExtractionRule } from "./model";
import { QuestionMarkCircleIcon } from "@heroicons/react/24/outline";
import { IoCheckmark } from "react-icons/io5";
import { HiMiniXMark } from "react-icons/hi2";
import { useState } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { useConfig } from "@/utils/hooks/useConfig";
import { useRouter } from "next/navigation";
import RunExtractionModal from "./run-extraction-modal";
import { extractNamedGroups } from "@/shared/lib/regex-utils";
import { useTranslations } from "next-intl";

const columnHelper = createColumnHelper<ExtractionRule>();

interface Props {
  extractions: ExtractionRule[];
  editCallback: (rule: ExtractionRule) => void;
}

export default function ExtractionsTable({ extractions, editCallback }: Props) {
  const t = useTranslations("extraction");
  const api = useApi();
  const { data: config } = useConfig();
  const { mutate } = useExtractions();
  const [expanded, setExpanded] = useState<ExpandedState>({});
  const [runModalRule, setRunModalRule] = useState<number | null>(null);
  const router = useRouter();

  const columns = [
    columnHelper.display({
      id: "priority",
      header: t("priority"),
      cell: (context) => context.row.original.priority,
    }),
    columnHelper.display({
      id: "name",
      header: t("name"),
      cell: ({ row }) => row.original.name,
    }),
    columnHelper.display({
      id: "description",
      header: t("description"),
      cell: (context) => context.row.original.description,
    }),
    columnHelper.display({
      id: "pre",
      header: t("preFormatting"),
      cell: (context) =>
        context.row.original.pre ? (
          <Icon icon={IoCheckmark} size="md" color="orange" />
        ) : (
          <Icon icon={HiMiniXMark} size="md" color="orange" />
        ),
    }),
    columnHelper.display({
      id: "attribute",
      header: t("attribute"),
      cell: (context) => context.row.original.attribute,
    }),
    columnHelper.display({
      id: "regex",
      header: () => (
        <div className="flex items-center">
          {t("regex")}{" "}
          <a
            href="https://docs.python.org/3.11/library/re.html#match-objects"
            target="_blank"
          >
            <Icon
              icon={QuestionMarkCircleIcon}
              variant="simple"
              color="gray"
              size="sm"
              tooltip={t("pythonRegexTooltip")}
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
          {t("condition")}{" "}
          <a
            href={`${
              config?.KEEP_DOCS_URL || "https://docs.keephq.dev"
            }/overview/enrichment/extraction`}
            target="_blank"
          >
            <Icon
              icon={QuestionMarkCircleIcon}
              variant="simple"
              color="gray"
              size="sm"
              tooltip={t("seeExtractionDocs")}
            />
          </a>
        </div>
      ),
      cell: (context) => context.row.original.condition,
    }),
    columnHelper.display({
      id: "newAttributes",
      header: t("extractedAttributes"),
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
    columnHelper.display({
      id: "actions",
      header: "",
      cell: (context) => (
        <div className="space-x-1 flex flex-row items-center justify-end opacity-0 group-hover:opacity-100 bg-slate-100 border-l">
          <Button
            color="orange"
            size="xs"
            icon={MdPlayArrow}
            tooltip={t("run")}
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
            tooltip={t("edit")}
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
            tooltip={t("delete")}
            onClick={(event) => {
              event.stopPropagation();
              deleteExtraction(context.row.original.id!);
            }}
          />
        </div>
      ),
      meta: {
        sticky: true,
      },
    }),
  ] as DisplayColumnDef<ExtractionRule>[];

  const table = useReactTable({
    getRowId: (row) => row.id.toString(),
    columns,
    data: extractions.sort((a, b) => b.priority - a.priority),
    state: { expanded },
    getCoreRowModel: getCoreRowModel(),
    onExpandedChange: setExpanded,
  });

  const deleteExtraction = (extractionId: number) => {
    if (confirm(t("confirmDeleteRule"))) {
      api
        .delete(`/extraction/${extractionId}`)
        .then(() => {
          mutate();
          toast.success(t("extractionDeletedSuccessfully"));
        })
        .catch((error: any) => {
          showErrorToast(error, t("failedToDeleteRule"));
        });
    }
  };

  return (
    <>
      <Table>
        <TableHead>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHeaderCell key={header.id}>
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
                className="hover:bg-slate-100 group cursor-pointer"
                key={row.id}
                onClick={() =>
                  router.push(`/extraction/${row.original.id}/executions`)
                }
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
                        <span className="font-bold">{t("createdAt")}:</span>
                        <span>
                          {new Date(
                            row.original.created_at + "Z"
                          ).toLocaleString()}
                        </span>
                      </div>
                      <div className="flex items-center space-x-2 pl-2.5">
                        <span className="font-bold">{t("createdBy")}:</span>
                        <span>{row.original.created_by}</span>
                      </div>
                      {row.original.updated_at && (
                        <>
                          <div className="flex items-center space-x-2 pl-2.5">
                            <span className="font-bold">{t("updatedAt")}:</span>
                            <span>
                              {new Date(
                                row.original.updated_at + "Z"
                              ).toLocaleString()}
                            </span>
                          </div>
                          <div className="flex items-center space-x-2 pl-2.5">
                            <span className="font-bold">{t("updatedBy")}:</span>
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

      <RunExtractionModal
        ruleId={runModalRule!}
        isOpen={runModalRule !== null}
        onClose={() => setRunModalRule(null)}
      />
    </>
  );
}
