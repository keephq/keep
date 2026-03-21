"use client";
import { useI18n } from "@/i18n/hooks/useI18n";

import { useState, use } from "react";
import { Card, Title, Icon, Subtitle } from "@tremor/react";
import { useEnrichmentEvents } from "@/utils/hooks/useEnrichmentEvents";
import { Link } from "@/components/ui";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import { useExtractions } from "@/utils/hooks/useExtractionRules";
import { ExecutionsTable } from "../../../../../components/table/ExecutionsTable";

interface Pagination {
  limit: number;
  offset: number;
}

export default function ExtractionExecutionsPage(props: {
  params: Promise<{ rule_id: string }>;
}) {
  const { t } = useI18n();
  const params = use(props.params);
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
          <Link href="/extraction">{t("rules.extraction.executions.allRules")}</Link>{" "}
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          {rule?.name || `Rule ${params.rule_id}`}
          <Icon icon={ArrowRightIcon} color="gray" size="xs" /> {t("rules.extraction.executions.title")}
        </Subtitle>
        <Title>{t("rules.extraction.executions.ruleExecutions")}</Title>
      </div>

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
    </div>
  );
}
