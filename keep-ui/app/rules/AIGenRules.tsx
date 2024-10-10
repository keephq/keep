import React, { useState, useEffect } from 'react';
import { Icon, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "@tremor/react";
import {
  createColumnHelper,
  getCoreRowModel,
  useReactTable,
  ColumnDef,
  getSortedRowModel,
  SortingState,
  flexRender,
  Header
} from "@tanstack/react-table";
import { useRulePusherUpdates, AIGeneratedRule, useGenRules } from "utils/hooks/useRules";
import { FaArrowDown, FaArrowRight, FaArrowUp, FaPlus, FaSpinner, FaSync } from "react-icons/fa";
import { InformationCircleIcon, ExclamationTriangleIcon, QuestionMarkCircleIcon } from "@heroicons/react/24/solid";
import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import useSWR, { mutate } from "swr";



const columnHelper = createColumnHelper<AIGeneratedRule>();

interface SortableHeaderCellProps {
  header: Header<AIGeneratedRule, unknown>;
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
        {children} {/* Column name or text */}
        {column.getCanSort() && (
          <>
            {/* Custom styled vertical line separator */}
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

export const AIGenRules: React.FC = () => {
  const {triggerGenRules } = useGenRules();
  const { data: session } = useSession();
  const [sorting, setSorting] = React.useState<SortingState>([]);

  const [isLoadingRules, setIsLoadingRules] = useState(true);
  const [generatedRules, setGeneratedRules] = useState<any>([]);

  const [loadingRows, setLoadingRows] = useState<{ [key: string]: boolean }>({});
  const [successRows, setSuccessRows] = useState<{ [key: string]: boolean }>({});

  const mutateAIGeneratedRules = (rules: AIGeneratedRule[]) => {
    setGeneratedRules(rules);
    setIsLoadingRules(false);
  };

  const { data:serverGenRules } = useRulePusherUpdates();

  useEffect(() => {
    console.log("serverGenRules", serverGenRules);

    if (Array.isArray(serverGenRules) && (0 === serverGenRules.length)) {
      return;
    }
    
    mutateAIGeneratedRules(serverGenRules);
  }, [serverGenRules]);

  const handleGenerateMoreRules = () => {
    setIsLoadingRules(true);
    triggerGenRules();
  };

  const handleAddRule = async (rule: AIGeneratedRule) => {
    const ruleKey = rule.ShortRuleName;
    setLoadingRows((prev) => ({ ...prev, [ruleKey]: true }));
    try {
      const temp = {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify({
          ruleName: rule.ShortRuleName,
          sqlQuery: { sql: '{new-version-not-adding-this}', params: ['no-params'] },
          celQuery: rule.CELRule,
          timeframeInSeconds: rule.Timeframe,
          timeUnit: 'minutes',
          groupingCriteria: rule.GroupBy,
          groupDescription: rule.ChainOfThought,
          requireApprove: false,
        }),
      };

      const apiUrl = getApiURL();
      const response = await fetch(`${apiUrl}/rules`, temp);

      if (response.ok) {
        setSuccessRows((prev) => ({ ...prev, [ruleKey]: true }));
        mutate(`${apiUrl}/rules`); // Refresh the rules list
      } else {
        const result = await response.json();
        console.error('Failed to add rule:', result);
      }
    } catch (error) {
      console.error('Error adding rule:', error);
    } finally {
      setLoadingRows((prev) => {
        const newLoadingRows = { ...prev };
        delete newLoadingRows[ruleKey];
        return newLoadingRows;
      });
    }
  };

  const columns = React.useMemo(() => [
    columnHelper.accessor("ShortRuleName", {
      header: "Short Rule Name",
    }),
    columnHelper.accessor("Score", {
      header: "Score",
    }),
    columnHelper.accessor("CELRule", {
      header: "CEL Rule",
      cell: (info) => <div className="text-wrap">{info.getValue()}</div>,
    }),
    columnHelper.accessor("Timeframe", {
      header: "Timeframe",
    }),
    columnHelper.accessor("GroupBy", {
      header: "Group By",
      cell: (info) => info.getValue().join(", "),
    }),
    columnHelper.accessor("ChainOfThought", {
      header: "Explanations",
      cell: (info) => {
        const rule = info.row.original;
        return (
          <div className="flex space-x-2">
            <Icon
              icon={InformationCircleIcon}
              tooltip={`Thinking behind the rule: ${rule.ChainOfThought}`}
              size="xs"
              color="gray"
              className="ml-1"
              variant="solid"
            />
            <Icon
              icon={ExclamationTriangleIcon}
              tooltip={`Why this rule is too general: ${rule.WhyTooGeneral}`}
              size="xs"
              color="gray"
              className="ml-1"
              variant="solid"
            />
            <Icon
              icon={QuestionMarkCircleIcon}
              tooltip={`Why this rule is too specific: ${rule.WhyTooSpecific}`}
              size="xs"
              color="gray"
              className="ml-1"
              variant="solid"
            />
          </div>
        );
      },
    }),
    columnHelper.display({
      id: 'add',
      header: 'Add',
      cell: (info) => {
        const rule = info.row.original;
        const ruleKey = rule.ShortRuleName;
        return (
          <div className="flex justify-center items-center">
            {loadingRows[ruleKey] ? (
              <FaSpinner className="animate-spin text-gray-500" />
            ) : successRows[ruleKey] ? (
              <div className="text-green-500">Added!</div>
            ) : (
              <button
                onClick={() => handleAddRule(rule)}
                className="text-blue-500 hover:text-blue-700"
              >
                <FaPlus /> 
              </button>
            )}
          </div>
        );
      },
    }),
  ] as ColumnDef<AIGeneratedRule>[], [loadingRows, successRows]);

  const table = useReactTable({
    columns,
    data: generatedRules?.results || [],
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: {
      sorting,
    },
  });

  if (isLoadingRules) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mb-4"></div>
          <p className="text-lg font-semibold">Loading AI recommendations...</p>
          <p className="text-sm text-gray-500">This may take a few moments</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col items-start">
        <button
          onClick={handleGenerateMoreRules}
          className="px-4 py-2 bg-orange-500 text-white rounded hover:bg-orange-600 flex items-center"
          disabled={isLoadingRules}
        >
          {isLoadingRules ? (
            <FaSpinner className="animate-spin mr-2" />
          ) : (
            <FaSync className="mr-2" />
          )}
          Generate more rules
        </button>
        <h2 className="text-xl font-semibold mt-4 self-center">AI Generated Rules</h2>
      </div>
      <p className="text-center">{generatedRules.summery}</p>
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
          {table.getRowModel().rows.map((row) => {
            const rule = row.original;
            const ruleKey = rule.ShortRuleName;
            return (
              <TableRow
                className={`${
                  successRows[ruleKey]
                    ? 'bg-green-100'
                    : 'even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted hover:bg-slate-100'
                } cursor-pointer`}
                key={row.id}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
};

export default AIGenRules;


