"use client";

import { useState } from "react";
import { MappingExecutionTable } from "../mapping-execution-table";
import { Card, Title } from "@tremor/react";
import { useMappingExecutions } from "@/utils/hooks/useMappingExecutions";

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

  const { executions, totalCount, isLoading } = useMappingExecutions({
    ruleId: params.rule_id,
    limit: pagination.limit,
    offset: pagination.offset,
  });

  if (isLoading) {
    return null;
  }

  return (
    <div className="p-4 space-y-4">
      <Title>Mapping Rule Executions</Title>
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
