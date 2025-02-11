"use client";

import { useState } from "react";
import { MappingExecutionTable } from "../mapping-execution-table";
import { Card, Title, Icon, Subtitle } from "@tremor/react";
import { useEnrichmentEvents } from "@/utils/hooks/useEnrichmentEvents";
import { Link } from "@/components/ui";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import { useMappings } from "@/utils/hooks/useMappingRules";

interface Pagination {
  limit: number;
  offset: number;
}

export default function MappingExecutionsPage({
  params,
}: {
  params: { rule_id: string };
}) {
  const [pagination, setPagination] = useState<Pagination>({
    limit: 20,
    offset: 0,
  });

  const { data: mappings } = useMappings();
  const rule = mappings?.find((m) => m.id === parseInt(params.rule_id));

  const { executions, totalCount, isLoading } = useEnrichmentEvents({
    ruleId: params.rule_id,
    limit: pagination.limit,
    offset: pagination.offset,
  });

  if (isLoading) {
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
