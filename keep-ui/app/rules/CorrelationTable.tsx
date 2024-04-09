import {
  Button,
  Card,
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
  CorrelationForm,
  CorrelationSidebar,
  DEFAULT_CORRELATION_FORM_VALUES,
} from "./CorrelationSidebar";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { parseCEL } from "react-querybuilder";
import { useRouter, useSearchParams } from "next/navigation";
import { FormattedQueryCell } from "./FormattedQueryCell";

const columnHelper = createColumnHelper<Rule>();

type CorrelationTableProps = {
  rules: Rule[];
};

export const CorrelationTable = ({ rules }: CorrelationTableProps) => {
  const router = useRouter();
  const searchParams = useSearchParams();

  const selectedId = searchParams ? searchParams.get("id") : null;
  const selectedRule = rules.find((rule) => rule.id === selectedId);
  const correlationFormFromRule: CorrelationForm = useMemo(() => {
    if (selectedRule) {
      return {
        name: selectedRule.name,
        description: "",
        timeAmount: selectedRule.timeframe,
        timeUnit: "seconds",
        groupedAttributes: selectedRule.grouping_criteria,
        query: parseCEL(selectedRule.definition_cel),
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
      columnHelper.display({
        id: "events",
        header: "Events",
      }),
      columnHelper.display({
        id: "alerts",
        header: "Alerts",
      }),
      columnHelper.accessor("definition_cel", {
        header: "Description",
        cell: (context) => (
          <FormattedQueryCell query={parseCEL(context.getValue())} />
        ),
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
            Dynamically incentivize cross-unit models without best-of-breed
            models.
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
                className="cursor-pointer hover:bg-slate-50"
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
