"use client";

import { Fragment, useState } from "react";
import {
  Card,
  Title,
  Icon,
  Subtitle,
  Badge,
  Text,
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
import { useExtractions } from "@/utils/hooks/useExtractionRules";
import TimeAgo from "react-timeago";
import { MappingExecutionTable } from "../../../mapping/[rule_id]/mapping-execution-table";

interface Pagination {
  limit: number;
  offset: number;
}

export default function ExtractionExecutionsPage({
  params,
}: {
  params: { rule_id: string };
}) {
  const [pagination, setPagination] = useState<Pagination>({
    limit: 20,
    offset: 0,
  });

  const { data: extractions } = useExtractions();
  const rule = extractions?.find((m) => m.id === parseInt(params.rule_id));

  const { executions, totalCount, isLoading } = useEnrichmentEvents({
    ruleId: params.rule_id,
    limit: pagination.limit,
    offset: pagination.offset,
    type: "extraction",
  });

  if (isLoading || !rule) {
    return null;
  }

  return (
    <div className="p-4 space-y-4">
      <div>
        <Subtitle className="text-sm">
          <Link href="/extraction">All Rules</Link>{" "}
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          {rule?.name || `Rule ${params.rule_id}`}
          <Icon icon={ArrowRightIcon} color="gray" size="xs" /> Executions
        </Subtitle>
        <Title>Extraction Rule Executions</Title>
      </div>

      <Card>
        <MappingExecutionTable
          executions={{
            items: executions,
            count: totalCount,
            limit: pagination.limit,
            offset: pagination.offset,
          }}
          setPagination={setPagination}
        />
      </Card>
    </div>
  );
}
