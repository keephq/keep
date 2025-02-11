"use client";

import { Card, Title, Badge } from "@tremor/react";
import { LogViewer } from "@/components/LogViewer";
import { getIcon } from "@/app/(keep)/workflows/[workflow_id]/workflow-execution-table";
import { useMappingExecutionDetail } from "@/utils/hooks/useMappingExecutions";

export default function MappingExecutionDetailsPage({
  params,
}: {
  params: { rule_id: string; execution_id: string };
}) {
  const { execution, isLoading } = useMappingExecutionDetail({
    ruleId: params.rule_id,
    executionId: params.execution_id,
  });

  if (isLoading || !execution) {
    return null;
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <Title>Execution Details</Title>
        <div className="flex items-center space-x-2">
          <span>Status:</span>
          {getIcon(execution.status)}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <Card>
            <Title>Logs</Title>
            <LogViewer logs={execution.logs || []} />
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <Title>Details</Title>
            <div className="space-y-2 mt-2">
              <div>
                <span className="text-gray-500">Execution ID:</span>
                <div>{execution.id}</div>
              </div>
              <div>
                <span className="text-gray-500">Alert ID:</span>
                <div>{execution.alert_id}</div>
              </div>
              <div>
                <span className="text-gray-500">Duration:</span>
                <div>
                  {execution.execution_time
                    ? `${execution.execution_time.toFixed(2)}s`
                    : "N/A"}
                </div>
              </div>
              {execution.error && (
                <div>
                  <span className="text-gray-500">Error:</span>
                  <div className="text-red-500">{execution.error}</div>
                </div>
              )}
            </div>
          </Card>

          {execution.enriched_fields && (
            <Card>
              <Title>Enriched Fields</Title>
              <div className="space-y-2 mt-2">
                {Object.entries(execution.enriched_fields).map(
                  ([key, value]) => (
                    <div key={key}>
                      <Badge color="orange" size="sm">
                        {key}
                      </Badge>
                      <div className="mt-1 text-sm">
                        {JSON.stringify(value)}
                      </div>
                    </div>
                  )
                )}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
