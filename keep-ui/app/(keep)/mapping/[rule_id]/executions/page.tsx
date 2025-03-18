"use client";

import { useState, use } from "react";
import { ExecutionsTable } from "../../../../../components/table/ExecutionsTable";
import {
  Card,
  Title,
  Icon,
  Subtitle,
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
} from "@tremor/react";
import { useEnrichmentEvents } from "@/utils/hooks/useEnrichmentEvents";
import { Link } from "@/components/ui";
import {
  ArrowRightIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from "@heroicons/react/16/solid";
import { useMappings } from "@/utils/hooks/useMappingRules";

interface Pagination {
  limit: number;
  offset: number;
}

export default function MappingExecutionsPage(props: {
  params: Promise<{ rule_id: string }>;
}) {
  const params = use(props.params);
  const [pagination, setPagination] = useState<Pagination>({
    limit: 20,
    offset: 0,
  });
  const [isDataPreviewExpanded, setIsDataPreviewExpanded] = useState(false);

  const { data: mappings } = useMappings();
  const rule = mappings?.find((m) => m.id === parseInt(params.rule_id));

  const { executions, totalCount, isLoading } = useEnrichmentEvents({
    ruleId: params.rule_id,
    limit: pagination.limit,
    offset: pagination.offset,
  });

  if (isLoading || !rule) {
    return null;
  }

  return (
    <div className="p-4 space-y-4">
      <div>
        <Subtitle className="text-sm">
          <Link href="/mapping">All Rules</Link>{" "}
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          {rule?.name || `Rule ${params.rule_id}`}
          <Icon icon={ArrowRightIcon} color="gray" size="xs" /> Executions
        </Subtitle>
        <Title>Mapping Rule Executions</Title>
      </div>

      <div className="space-y-4">
        <Card>
          <ExecutionsTable
            executions={{
              items: executions,
              count: totalCount,
              limit: pagination.limit,
              offset: pagination.offset,
            }}
            setPagination={setPagination}
          />
        </Card>
        {rule.type === "csv" && rule.rows && rule.rows.length > 0 && (
          <Card>
            <div
              className="flex justify-between items-center cursor-pointer"
              onClick={() => setIsDataPreviewExpanded(!isDataPreviewExpanded)}
            >
              <Title>Data Preview</Title>
              <Icon
                icon={isDataPreviewExpanded ? ChevronUpIcon : ChevronDownIcon}
                color="gray"
                size="xs"
              />
            </div>
            {isDataPreviewExpanded && (
              <div className="mt-4 max-h-96 overflow-auto">
                <Table>
                  <TableHead>
                    <TableRow>
                      {Object.keys(rule.rows[0]).map((key) => (
                        <TableHeaderCell key={key}>{key}</TableHeaderCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {rule.rows.slice(0, 5).map((row, idx) => (
                      <TableRow key={idx}>
                        {Object.values(row).map((value: any, valueIdx) => (
                          <TableCell key={valueIdx}>
                            {JSON.stringify(value)}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
