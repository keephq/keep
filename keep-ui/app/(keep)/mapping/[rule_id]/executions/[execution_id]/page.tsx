"use client";

import { Card, Title, Badge, Icon, Subtitle } from "@tremor/react";
import { LogViewer } from "@/components/LogViewer";
import { getIcon } from "@/app/(keep)/workflows/[workflow_id]/workflow-execution-table";
import { useEnrichmentEvent } from "@/utils/hooks/useEnrichmentEvents";
import { Link } from "@/components/ui";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import { useMappings } from "@/utils/hooks/useMappingRules";

export default function MappingExecutionDetailsPage({
  params,
}: {
  params: { rule_id: string; execution_id: string };
}) {
  const { execution, isLoading } = useEnrichmentEvent({
    ruleId: params.rule_id,
    executionId: params.execution_id,
  });

  const { data: mappings } = useMappings();
  const rule = mappings?.find((m) => m.id === parseInt(params.rule_id));

  if (isLoading || !execution) {
    return null;
  }

  const alertFilterUrl = `/alerts/feed?cel=${encodeURIComponent(
    `id=="${execution.enrichment_event.alert_id}"`
  )}`;

  return (
    <div className="p-4 space-y-4">
      <div>
        <Subtitle className="text-sm">
          <Link href="/mapping">All Rules</Link>{" "}
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          {rule?.name || `Rule ${params.rule_id}`}{" "}
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          <Link href={`/mapping/${params.rule_id}/executions`}>Executions</Link>{" "}
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          {execution.enrichment_event.id}
        </Subtitle>
        <div className="flex items-center justify-between">
          <Title>Execution Details</Title>
          <div className="flex items-center space-x-2">
            <span>Status:</span>
            {getIcon(execution.enrichment_event.status)}
          </div>
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
            <div className="mb-2.5">
              <span className="text-gray-500 text-xs">
                Alert ID:{" "}
                <Link
                  href={alertFilterUrl}
                  className="text-orange-500 hover:text-orange-600"
                >
                  {execution.enrichment_event.alert_id}
                </Link>
              </span>
            </div>
            <Title>Enriched Fields</Title>
            <div className="space-y-2 mt-2">
              {Object.entries(
                execution.enrichment_event.enriched_fields || {}
              ).map(([key, value]) => (
                <div key={key}>
                  <Badge color="orange" size="sm">
                    {key}
                  </Badge>
                  <div className="mt-1 text-sm">{JSON.stringify(value)}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
