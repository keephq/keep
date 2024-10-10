import {
  Badge,
  Button,
  Card, Icon,
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
  getSortedRowModel,
  useReactTable,
  SortingState,
} from "@tanstack/react-table";
import { DefaultRuleGroupType, parseCEL } from "react-querybuilder";
import { useRouter, useSearchParams } from "next/navigation";
import { FormattedQueryCell } from "./FormattedQueryCell";
import { DeleteRuleCell } from "./CorrelationSidebar/DeleteRule";
import {PlusIcon} from "@radix-ui/react-icons";
import { Tab, TabGroup, TabList, TabPanel, TabPanels } from "@tremor/react";
import { BoltIcon, SparklesIcon } from "@heroicons/react/24/outline";
import { AIGenRules } from './AIGenRules'; // Add this import at the top of the file
import { FaArrowDown, FaArrowRight, FaArrowUp } from "react-icons/fa";
import { Header } from "@tanstack/react-table"; // Ensure this import is present

const TIMEFRAME_UNITS_FROM_SECONDS= {
  seconds: (amount: number) => amount,
  minutes: (amount: number) => amount / 60,
  hours: (amount: number) => amount / 3600,
  days: (amount: number) => amount  / 86400,
} as const;

const columnHelper = createColumnHelper<Rule>();

type CorrelationTableProps = {
  rules: Rule[];
};

interface SortableHeaderCellProps {
  header: Header<Rule, unknown>;
  children: React.ReactNode;
}

const SortableHeaderCell: React.FC<SortableHeaderCellProps> = ({
  header,
  children,
}) => {
  const { column } = header;

  return (
    <TableHeaderCell
      className={`relative ${column.getIsPinned() ? "" : "hover:bg-slate-100"} group`}
    >
      <div className="flex items-center">
        {children}
        {column.getCanSort() && (
          <>
            <div className="w-px h-5 mx-2 bg-gray-400"></div>
            <Icon
              className="cursor-pointer"
              size="xs"
              color="neutral"
              onClick={(event) => {
                event.stopPropagation();
                const toggleSorting = header.column.getToggleSortingHandler();
                if (toggleSorting) toggleSorting(event);
              }}
              tooltip={
                column.getNextSortingOrder() === "asc"
                  ? "Sort ascending"
                  : column.getNextSortingOrder() === "desc"
                  ? "Sort descending"
                  : "Clear sort"
              }
              icon={column.getIsSorted() ? (
                column.getIsSorted() === "asc" ? FaArrowDown : FaArrowUp
              ) : (
                FaArrowRight
              )}
            />
          </>
        )}
      </div>
    </TableHeaderCell>
  );
};

export const CorrelationTable = ({ rules }: CorrelationTableProps) => {
  const router = useRouter();
  const searchParams = useSearchParams();

  const selectedId = searchParams ? searchParams.get("id") : null;
  const selectedRule = rules.find((rule) => rule.id === selectedId);
  const correlationFormFromRule: CorrelationForm = useMemo(() => {
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
        timeAmount: TIMEFRAME_UNITS_FROM_SECONDS[timeunit](selectedRule.timeframe),
        timeUnit: timeunit,
        groupedAttributes: selectedRule.grouping_criteria,
        requireApprove: selectedRule.require_approve,
        resolveOn: selectedRule.resolve_on,
        query: queryInGroup,
        incidents: selectedRule.incidents,
      };
    }

    return DEFAULT_CORRELATION_FORM_VALUES;
  }, [selectedRule]);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedTab, setSelectedTab] = useState<string>("existing");
  const [isAIGenRulesLoaded, setIsAIGenRulesLoaded] = useState(false);
  const [sorting, setSorting] = useState<SortingState>([]);

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
        header: "CEL Rule",
      }),
      columnHelper.accessor("grouping_criteria", {
        header: "Grouped by",
        cell: (context) => (
          context.getValue().map((group, index) =>
            <>
              <Badge color="orange" key={group}>{group}</Badge>
              {context.getValue().length !== index + 1 && (
              <Icon  icon={PlusIcon} size="xs" color="slate" />
            )}
            </>
          )
        ),
      }),
      columnHelper.accessor("incidents", {
        header: "Incidents",
        cell: (context) => (
          context.getValue()
        ),
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
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: {
      sorting,
    },
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
      <TabGroup className="mt-6">
        <TabList color="orange">
          <Tab icon={BoltIcon} onClick={() => setSelectedTab("existing")}>
            Existing Correlations
          </Tab>
          <Tab
            icon={SparklesIcon}
            onClick={() => {
              setSelectedTab("ai-suggestions");
              setIsAIGenRulesLoaded(true);
            }}
          >
            AI Suggestions
          </Tab>
        </TabList>
        <TabPanels>
          <TabPanel>
            <Card className="mt-4">
              <Table>
                <TableHead>
                  {table.getHeaderGroups().map((headerGroup) => (
                    <TableRow
                      className="border-b border-tremor-border dark:border-dark-tremor-border"
                      key={headerGroup.id}
                    >
                      {headerGroup.headers.map((header) => (
                        <SortableHeaderCell
                          header={header}
                          key={header.id}
                        >
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                        </SortableHeaderCell>
                      ))}
                    </TableRow>
                  ))}
                </TableHead>
                <TableBody>
                  {table.getRowModel().rows.map((row) => (
                    <TableRow
                      key={row.id}
                      className="cursor-pointer even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted hover:bg-slate-100"
                      onClick={() => router.push(`?id=${row.original.id}`)}
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
            </Card>
          </TabPanel>
          <TabPanel>
            <Card className="mt-4">
              <div className="p-4 text-center text-gray-500">
                {isAIGenRulesLoaded ? <AIGenRules /> : null}
              </div>
            </Card>
          </TabPanel>
        </TabPanels>
      </TabGroup>
      <CorrelationSidebar
        isOpen={isSidebarOpen}
        toggle={onCloseCorrelation}
        defaultValue={correlationFormFromRule}
      />
    </div>
  );
};