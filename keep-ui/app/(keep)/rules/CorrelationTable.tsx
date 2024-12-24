import {
  Badge,
  Button,
  Card,
  Icon,
  Subtitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Title,
} from "@tremor/react";
import { useEffect, useMemo, useState } from "react";
import { Rule } from "utils/hooks/useRules";
import {
  CorrelationSidebar,
  DEFAULT_CORRELATION_FORM_VALUES,
} from "./CorrelationSidebar";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { DefaultRuleGroupType, parseCEL } from "react-querybuilder";
import { useRouter, useSearchParams } from "next/navigation";
import { FormattedQueryCell } from "./FormattedQueryCell";
import { DeleteRuleCell } from "./CorrelationSidebar/DeleteRule";
import { PlusIcon } from "@radix-ui/react-icons";
import { CorrelationFormType } from "./CorrelationSidebar/types";

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
  const correlationFormFromRule: CorrelationFormType = useMemo(() => {
    if (selectedRule) {
      const query = parseCEL(selectedRule.definition_cel);
      const anyCombinator = query.rules.some((rule) => "combinator" in rule);

      const queryInGroup: DefaultRuleGroupType = {
        ...query,
        rules: anyCombinator
          ? query.rules
          : [
              {
                combinator: "and",
                rules: query.rules,
              },
            ],
      };

      const timeunit = selectedRule.timeunit ?? "seconds";

      return {
        name: selectedRule.name,
        description: selectedRule.group_description ?? "",
        timeAmount: TIMEFRAME_UNITS_FROM_SECONDS[timeunit](
          selectedRule.timeframe
        ),
        timeUnit: timeunit,
        groupedAttributes: selectedRule.grouping_criteria,
        requireApprove: selectedRule.require_approve,
        resolveOn: selectedRule.resolve_on,
        createOn: selectedRule.create_on,
        query: queryInGroup,
        incidents: selectedRule.incidents,
      };
    }

    return DEFAULT_CORRELATION_FORM_VALUES;
  }, [selectedRule]);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const onCorrelationClick = () => {
    setIsSidebarOpen(true);
  };

  const onCloseCorrelation = () => {
    setIsSidebarOpen(false);
    router.replace("/rules");
  };

  useEffect(() => {
    if (selectedRule) {
      onCorrelationClick();
    } else {
      router.replace("/rules");
    }
  }, [selectedRule, router]);

  const CORRELATION_TABLE_COLS = useMemo(
    () => [
      columnHelper.accessor("name", {
        header: "Correlation Name",
      }),
      columnHelper.accessor("definition_cel", {
        header: "Description",
        cell: (context) => (
          <FormattedQueryCell query={parseCEL(context.getValue())} />
        ),
      }),
      columnHelper.accessor("grouping_criteria", {
        header: "Grouped by",
        cell: (context) =>
          context.getValue().map((group, index) => (
            <>
              <Badge color="orange" key={group}>
                {group}
              </Badge>
              {context.getValue().length !== index + 1 && (
                <Icon icon={PlusIcon} size="xs" color="slate" />
              )}
            </>
          )),
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
    data: rules,
    columns: CORRELATION_TABLE_COLS,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="flex-1 flex flex-col h-full">
      <div className="flex items-center justify-between">
        <div>
          <Title className="text-2xl font-normal">
            Correlations <span className="text-gray-400">({rules.length})</span>
          </Title>
          <Subtitle className="text-gray-400">
            Manually setup flexible rules for alert to incident correlation
          </Subtitle>
        </div>
        <Button color="orange" onClick={() => onCorrelationClick()}>
          Create Correlation
        </Button>
      </div>
      <Card className="flex-1 mt-10">
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
      <CorrelationSidebar
        isOpen={isSidebarOpen}
        toggle={onCloseCorrelation}
        defaultValue={correlationFormFromRule}
      />
    </div>
  );
};
