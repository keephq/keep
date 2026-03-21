"use client";
import { useI18n } from "@/i18n/hooks/useI18n";

import { Icon } from "@tremor/react";
import { useParams } from "next/navigation";
import { Link } from "@/components/ui";
import { Subtitle } from "@tremor/react";
import { ArrowRightIcon } from "@heroicons/react/16/solid";

export function WorkflowBreadcrumbs({ workflowId }: { workflowId: string }) {
  const { t } = useI18n();
  const clientParams = useParams();

  return (
    <Subtitle className="text-sm">
      <Link href="/workflows">{t("workflows.breadcrumbs.allWorkflows")}</Link>{" "}
      {clientParams.workflow_execution_id ? (
        <>
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          <Link href={`/workflows/${workflowId}`}>{t("workflows.breadcrumbs.workflowDetails")}</Link>
          <Icon icon={ArrowRightIcon} color="gray" size="xs" /> {t("workflows.breadcrumbs.workflowExecutionDetails")}
        </>
      ) : (
        <>
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          <Link href={`/workflows/${workflowId}`}>{t("workflows.breadcrumbs.workflowDetails")}</Link>
        </>
      )}
      {clientParams.revision && (
        <>
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          <Link
            href={`/workflows/${workflowId}/versions/${clientParams.revision}`}
          >
            {t("workflows.breadcrumbs.workflowRevision", { revision: clientParams.revision })}
          </Link>
        </>
      )}
    </Subtitle>
  );
}
