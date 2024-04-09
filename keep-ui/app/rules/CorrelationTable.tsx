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
  CreateCorrelationSidebar,
  DEFAULT_CORRELATION_FORM_VALUES,
} from "./CreateCorrelationSidebar";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { parseCEL } from "react-querybuilder";
import { useRouter, useSearchParams } from "next/navigation";

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

  const onCreateCorrelationClick = () => {
    setIsSidebarOpen(true);
  };

  const onCloseCreateCorrelation = () => {
    setIsSidebarOpen(false);
    router.replace("/rules");
  };

  useEffect(() => {
    if (selectedRule) {
      onCreateCorrelationClick();
    }
  }, [selectedRule]);

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
        cell: (context) => JSON.stringify(parseCEL(context.getValue())),
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
        <Button color="orange" onClick={() => onCreateCorrelationClick()}>
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
              <TableRow key={row.id} className="cursor-pointer">
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
      <CreateCorrelationSidebar
        isOpen={isSidebarOpen}
        toggle={onCloseCreateCorrelation}
        defaultValue={correlationFormFromRule}
      />
    </div>
  );
};
