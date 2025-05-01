import {
  Badge,
  Button,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import { useEffect, useMemo, useState } from "react";
import { Rule } from "utils/hooks/useRules";
import { CorrelationSidebar } from "./CorrelationSidebar";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { DefaultRuleGroupType } from "react-querybuilder";
import { parseCEL } from "react-querybuilder/parseCEL";
import { useRouter, useSearchParams } from "next/navigation";
import { FormattedQueryCell } from "./FormattedQueryCell";
import { DeleteRuleCell } from "./CorrelationSidebar/DeleteRule";
import { CorrelationFormType } from "./CorrelationSidebar/types";
import { PageSubtitle, PageTitle } from "@/shared/ui";
import { PlusIcon } from "@heroicons/react/20/solid";
import { GroupedByCell } from "./GroupedByCel";
import CelInput from "@/features/cel-input/cel-input";

const TIMEFRAME_UNITS_FROM_SECONDS = {
  seconds: (amount: number) => amount,
  minutes: (amount: number) => amount / 60,
  hours: (amount: number) => amount / 3600,
  days: (amount: number) => amount / 86400,
} as const;

const columnHelper = createColumnHelper<Rule>();

type CorrelationTableProps = {
  rules: Rule[];
};

export const CorrelationTable = ({ rules }: CorrelationTableProps) => {
  const router = useRouter();
  const searchParams = useSearchParams();

  const selectedId = searchParams ? searchParams.get("id") : null;
  const selectedRule = rules.find((rule) => rule.id === selectedId);

  const [isRuleCreation, setIsRuleCreation] = useState(false);

  const onCloseCorrelation = () => {
    setIsRuleCreation(false);
    router.replace("/rules");
  };

  const CORRELATION_TABLE_COLS = useMemo(
    () => [
      columnHelper.accessor("name", {
        header: "Correlation Name",
        cell: (context) => {
          return (
            <div
              title={context.getValue()}
              className="max-w-28 md:max-w-40 overflow-hidden overflow-ellipsis"
            >
              {context.getValue()}
            </div>
          );
        },
      }),
      columnHelper.accessor("incident_name_template", {
        header: "Incident Name Template",
        cell: (context) => {
          const template = context.getValue();
          return template ? (
            <Badge title={context.getValue() as string} color="orange">
              {
                <div className="max-w-28 md:max-w-40 2xl:max-w-96 overflow-hidden overflow-ellipsis">
                  {template}
                </div>
              }
            </Badge>
          ) : (
            <Badge color="gray">default</Badge>
          );
        },
      }),
      columnHelper.accessor("incident_prefix", {
        header: "Incident Prefix",
        cell: (context) =>
          context.getValue() && (
            <Badge color="orange">{context.getValue()}</Badge>
          ),
      }),
      columnHelper.accessor("definition_cel", {
        header: "Description",
        cell: (context) => {
          let cel = context.getValue();
          if (cel.startsWith("(") && cel.endsWith(")")) {
            cel = cel.slice(1, -1);
          }
          return (
            <div
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
            >
              <CelInput readOnly={true} value={cel}></CelInput>
            </div>
          );
        },
      }),
      columnHelper.accessor("grouping_criteria", {
        header: "Grouped by",
        cell: (context) => (
          <GroupedByCell fields={context.getValue()}></GroupedByCell>
        ),
      }),
      columnHelper.accessor("incidents", {
        header: "Incidents",
        cell: (context) => context.getValue(),
      }),
      columnHelper.display({
        id: "menu",
        cell: (context) => <DeleteRuleCell ruleId={context.row.original.id} />,
      }),
    ],
    []
  );

  const table = useReactTable({
    getRowId: (row) => row.id,
    data: rules,
    columns: CORRELATION_TABLE_COLS,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="flex-1 flex flex-col h-full gap-6">
      <div className="flex items-center justify-between">
        <div>
          <PageTitle>
            Correlations <span className="text-gray-400">({rules.length})</span>
          </PageTitle>
          <PageSubtitle>
            Manually setup flexible rules for alert to incident correlation
          </PageSubtitle>
        </div>
        <Button
          color="orange"
          size="md"
          variant="primary"
          onClick={() => setIsRuleCreation(true)}
          icon={PlusIcon}
        >
          Create correlation
        </Button>
      </div>
      <Card className="p-0">
        <Table>
          <TableHead>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow
                key={headerGroup.id}
                className="border-b border-slate-200"
              >
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
              <TableRow
                key={row.id}
                className="cursor-pointer hover:bg-slate-50 group"
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell
                    key={cell.id}
                    onClick={() => router.push(`?id=${cell.row.original.id}`)}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
      {(isRuleCreation || !!selectedRule) && (
        <CorrelationSidebar
          isOpen={true}
          toggle={onCloseCorrelation}
          selectedRule={selectedRule}
        />
      )}
    </div>
  );
};
