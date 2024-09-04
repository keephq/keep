import React, { useEffect, useMemo, useState } from 'react';
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
  Badge,
  SparkAreaChart,
} from "@tremor/react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { DeduplicationRule } from "app/deduplication/models";
import DeduplicationSidebar from "app/deduplication/DeduplicationSidebar";
import { TrashIcon, PauseIcon, PlusIcon } from "@heroicons/react/24/outline";
import Image from "next/image";

const columnHelper = createColumnHelper<DeduplicationRule>();

type DeduplicationTableProps = {
  deduplicationRules: DeduplicationRule[];
};

export const DeduplicationTable: React.FC<DeduplicationTableProps> = ({ deduplicationRules }) => {
  const router = useRouter();
  const searchParams = useSearchParams();

  const selectedId = searchParams ? searchParams.get("id") : null;
  const selectedRule = deduplicationRules.find((rule) => rule.id === selectedId);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedDeduplicationRule, setSelectedDeduplicationRule] = useState<DeduplicationRule | null>(null);

  const deduplicationFormFromRule = useMemo(() => {
    if (selectedDeduplicationRule) {
      return {
        name: selectedDeduplicationRule.name,
        description: selectedDeduplicationRule.description,
        timeUnit: "seconds",
      };
    }

    return {};
  }, [selectedDeduplicationRule]);

  const onDeduplicationClick = (rule: DeduplicationRule) => {
    setSelectedDeduplicationRule(rule);
    setIsSidebarOpen(true);
  };

  const onCloseDeduplication = () => {
    setIsSidebarOpen(false);
    setSelectedDeduplicationRule(null);
  };

  useEffect(() => {
    if (selectedRule) {
      onDeduplicationClick(selectedRule);
    }
  }, [selectedRule]);

  const DEDUPLICATION_TABLE_COLS = useMemo(
    () => [
      columnHelper.accessor("provider_type", {
        header: "",
        cell: (info) => (
          <div className="flex items-center">
            <Image
              className="inline-block"
              key={info.getValue()}
              alt={info.getValue()}
              height={24}
              width={24}
              title={info.getValue()}
              src={`/icons/${info.getValue()}-icon.png`}
            />
          </div>
        ),
      }),
      columnHelper.accessor("description", {
        header: "Name",
        cell: (info) => (
          <div className="flex items-center justify-between max-w-[300px]">
            <span className="truncate lg:whitespace-normal">{info.getValue()}</span>
            {info.row.original.default && (
              <Badge color="orange" size="xs" className="ml-2">Default</Badge>
            )}
          </div>
        ),
      }),
      columnHelper.accessor("alertsDigested", {
        header: "Digested",
        cell: (info) => <Badge color="orange" className="w-16">{info.getValue() || 0}</Badge>,
      }),
      columnHelper.accessor("dedupRatio", {
        header: "Dedup Ratio",
        cell: (info) => <Badge color="orange" className="w-16">{info.getValue() || "N/A"}</Badge>,
      }),
      columnHelper.accessor("distribution", {
        header: "Distribution",
        cell: (info) => (
          <SparkAreaChart
            data={info.getValue()}
            categories={["value"]}
            index="date"
            className="h-10 w-36"
          />
        ),
      }),
      columnHelper.accessor("default_fingerprint_fields", {
        header: "Fields",
        cell: (info) => (
          <div className="flex flex-wrap items-center gap-2 max-w-[350px]">
            {info.getValue().map((field: string, index: number) => (
              <React.Fragment key={field}>
                {index > 0 && <PlusIcon className="w-4 h-4 text-gray-400" />}
                <Badge color="orange" size="md">{field}</Badge>
              </React.Fragment>
            ))}
          </div>
        ),
      }),
      columnHelper.display({
        id: "actions",
        cell: (info) => (
          <div className="flex space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button
              size="xs"
              variant="secondary"
              icon={PauseIcon}
              tooltip="Disable Rule"
            />
            <Button
              size="xs"
              variant="secondary"
              icon={TrashIcon}
              tooltip="Delete Rule"
            />
          </div>
        ),
      }),
    ],
    []
  );

  const table = useReactTable({
    data: deduplicationRules,
    columns: DEDUPLICATION_TABLE_COLS,
    getCoreRowModel: getCoreRowModel(),
  })

  const handleSubmitDeduplicationRule = async (data: Partial<DeduplicationRule>) => {
    // Implement the logic to submit the deduplication rule
    // This is a placeholder function, replace with actual implementation
    console.log("Submitting deduplication rule:", data);
    // Add API call or state update logic here
  };

  return (
    <div className="flex-1 flex flex-col h-full">
      <div className="flex items-center justify-between">
        <div>
          <Title className="text-2xl font-normal">
            Deduplication Rules <span className="text-gray-400">({deduplicationRules.length})</span>
          </Title>
          <Subtitle className="text-gray-400">
            Set up rules to deduplicate similar alerts
          </Subtitle>
        </div>
        <Button color="orange" onClick={() => onDeduplicationClick({} as DeduplicationRule)}>
          Create Deduplication Rule
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
                onClick={() => onDeduplicationClick(row.original)}
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
      <DeduplicationSidebar
        isOpen={isSidebarOpen}
        toggle={onCloseDeduplication}
        defaultValue={deduplicationFormFromRule}
        onSubmit={handleSubmitDeduplicationRule}
      />
    </div>
  );
};
