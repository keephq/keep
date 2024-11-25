import React, { useEffect, useMemo, useState } from "react";
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
import { Tooltip } from "@/shared/ui/Tooltip";
import { useRouter, useSearchParams } from "next/navigation";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { DeduplicationRule } from "@/app/(keep)/deduplication/models";
import DeduplicationSidebar from "@/app/(keep)/deduplication/DeduplicationSidebar";
import {
  TrashIcon,
  PauseIcon,
  PlusIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import Image from "next/image";
import { useApiUrl } from "utils/hooks/useConfig";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";

const columnHelper = createColumnHelper<DeduplicationRule>();

import { KeyedMutator } from "swr";

type DeduplicationTableProps = {
  deduplicationRules: DeduplicationRule[];
  mutateDeduplicationRules: KeyedMutator<DeduplicationRule[]>;
};

export const DeduplicationTable: React.FC<DeduplicationTableProps> = ({
  deduplicationRules,
  mutateDeduplicationRules,
}) => {
  const router = useRouter();
  const { data: session } = useSession();
  const searchParams = useSearchParams();
  const apiUrl = useApiUrl();

  let selectedId = searchParams ? searchParams.get("id") : null;
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedDeduplicationRule, setSelectedDeduplicationRule] =
    useState<DeduplicationRule | null>(null);

  const onDeduplicationClick = (rule: DeduplicationRule) => {
    setSelectedDeduplicationRule(rule);
    setIsSidebarOpen(true);
    router.push(`/deduplication?id=${rule.id}`);
  };

  const onCloseDeduplication = () => {
    setIsSidebarOpen(false);
    setSelectedDeduplicationRule(null);
    router.push("/deduplication");
  };

  const handleDeleteRule = async (
    rule: DeduplicationRule,
    event: React.MouseEvent
  ) => {
    event.stopPropagation();
    if (rule.default) return; // Don't delete default rules

    if (
      window.confirm("Are you sure you want to delete this deduplication rule?")
    ) {
      try {
        const url = `${apiUrl}/deduplications/${rule.id}`;
        const response = await fetch(url, {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
          },
        });

        if (response.ok) {
          await mutateDeduplicationRules();
        } else {
          console.error("Failed to delete deduplication rule");
        }
      } catch (error) {
        console.error("Error deleting deduplication rule:", error);
      }
    }
  };

  useEffect(() => {
    if (selectedId && !isSidebarOpen) {
      const rule = deduplicationRules.find((r) => r.id === selectedId);
      if (rule) {
        setSelectedDeduplicationRule(rule);
        setIsSidebarOpen(true);
      }
    }
  }, [selectedId, deduplicationRules]);

  useEffect(() => {
    if (!isSidebarOpen && selectedId) {
      router.push("/deduplication");
    }
  }, [isSidebarOpen, selectedId, router]);

  const TOOLTIPS = {
    distribution:
      "Displays the number of alerts processed hourly over the last 24 hours. A consistent or high distribution indicates steady activity for this deduplication rule.",
    dedup_ratio:
      "Represents the percentage of alerts successfully deduplicated. Higher values indicate better deduplication efficiency, meaning fewer redundant alerts.",
  };

  const DEDUPLICATION_TABLE_COLS = useMemo(
    () => [
      columnHelper.accessor("provider_type", {
        header: "",
        cell: (info) => (
          <div className="flex items-center w-8">
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
        header: "Description",
        cell: (info) => (
          <div className="flex items-center justify-between max-w-[320px]">
            <span className="truncate lg:whitespace-normal">
              {info.row.original.provider_id ?? "Keep"} {" "} deduplication rule
            </span>
            {info.row.original.default ? (
              <Badge color="orange" size="xs" className="ml-2">
                Default
              </Badge>
            ) : (
              <Badge color="orange" size="xs" className="ml-2">
                Custom
              </Badge>
            )}
            {info.row.original.full_deduplication && (
              <Badge color="orange" size="xs" className="ml-2">
                Full Deduplication
              </Badge>
            )}
          </div>
        ),
      }),
      columnHelper.accessor("ingested", {
        header: "Ingested",
        cell: (info) => (
          <Badge color="orange" className="w-16">
            {info.getValue() || 0}
          </Badge>
        ),
      }),
      columnHelper.accessor("dedup_ratio", {
        header: "Dedup Ratio",
        cell: (info) => {
          let formattedValue;
          if (info.row.original.ingested === 0) {
            formattedValue = "Unknown yet";
          } else {
            const value = info.getValue() || 0;
            formattedValue = `${Number(value).toFixed(1)}%`;
          }
          return (
            <Badge color="orange" className="w-fit">
              {formattedValue}
            </Badge>
          );
        },
      }),
      columnHelper.accessor("distribution", {
        header: "Distribution",
        cell: (info) => {
          const rawData = info.getValue();
          const maxNumber = Math.max(...rawData.map((item) => item.number));
          const allZero = rawData.every((item) => item.number === 0);
          const data = rawData.map((item) => ({
            ...item,
            number: maxNumber > 0 ? item.number / maxNumber + 1 : 0.5,
          }));
          const colors = ["orange"];
          const showGradient = true;
          return (
            <SparkAreaChart
              data={data}
              categories={["number"]}
              index="hour"
              className="h-10 w-36"
              colors={colors}
              showGradient={showGradient}
              minValue={allZero ? 0 : undefined}
              maxValue={allZero ? 1 : undefined}
            />
          );
        },
      }),
      columnHelper.accessor("fingerprint_fields", {
        header: "Fields",
        cell: (info) => {
          const fields = info.getValue();
          const ignoreFields = info.row.original.ignore_fields;
          const displayFields =
            fields && fields.length > 0 ? fields : ignoreFields;

          if (!displayFields || displayFields.length === 0) {
            return (
              <div className="flex flex-wrap items-center gap-2 w-[200px]">
                <Badge color="orange" size="md">
                  N/A
                </Badge>
              </div>
            );
          }

          return (
            <div className="flex flex-wrap items-center gap-2 w-[200px]">
              {displayFields.map((field: string, index: number) => (
                <React.Fragment key={field}>
                  {index > 0 && <PlusIcon className="w-4 h-4 text-gray-400" />}
                  <Badge color="orange" size="md">
                    {field}
                  </Badge>
                </React.Fragment>
              ))}
            </div>
          );
        },
      }),
      columnHelper.display({
        id: "actions",
        cell: (info) => (
          <div className="flex justify-end space-x-1 opacity-0 group-hover:opacity-100 transition-opacity w-full">
            {/* <Button
              size="xs"
              variant="secondary"
              icon={PauseIcon}
              tooltip="Disable Rule"
            /> */}
            <Button
              size="xs"
              variant="secondary"
              icon={TrashIcon}
              tooltip={
                info.row.original.default
                  ? "Cannot delete default rule"
                  : "Delete Rule"
              }
              disabled={info.row.original.default}
              onClick={(e) => handleDeleteRule(info.row.original, e)}
            />
          </div>
        ),
      }),
    ],
    [handleDeleteRule]
  );

  const table = useReactTable({
    data: deduplicationRules,
    columns: DEDUPLICATION_TABLE_COLS,
    getCoreRowModel: getCoreRowModel(),
  });

  const handleSubmitDeduplicationRule = async (
    data: Partial<DeduplicationRule>
  ) => {
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
            Deduplication Rules{" "}
            <span className="text-gray-400">
              ({deduplicationRules?.length})
            </span>
          </Title>
          <Subtitle className="text-gray-400">
            Set up rules to deduplicate similar alerts
          </Subtitle>
        </div>
        <Button
          color="orange"
          onClick={() => {
            setSelectedDeduplicationRule(null);
            setIsSidebarOpen(true);
          }}
        >
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
                    <span className="flex items-center">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      {Object.keys(TOOLTIPS).includes(header.id) && (
                        <Tooltip
                          content={
                            <>{TOOLTIPS[header.id as keyof typeof TOOLTIPS]}</>
                          }
                          className="z-50"
                        >
                          <QuestionMarkCircleIcon className="w-4 h-4 ml-1" />
                        </Tooltip>
                      )}
                    </span>
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
        mutateDeduplicationRules={mutateDeduplicationRules}
        isOpen={isSidebarOpen}
        toggle={onCloseDeduplication}
        selectedDeduplicationRule={selectedDeduplicationRule}
        onSubmit={handleSubmitDeduplicationRule}
      />
    </div>
  );
};
