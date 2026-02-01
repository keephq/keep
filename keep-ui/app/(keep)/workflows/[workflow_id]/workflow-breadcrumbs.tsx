"use client";

import { Icon } from "@tremor/react";
import { useParams } from "next/navigation";
import { Link } from "@/components/ui";
import { Subtitle } from "@tremor/react";
import { ArrowRightIcon } from "@heroicons/react/16/solid";

export function WorkflowBreadcrumbs({ workflowId }: { workflowId: string }) {
  const clientParams = useParams();

  return (
    <Subtitle className="text-sm">
      <Link href="/workflows">All Workflows</Link>{" "}
      {clientParams.workflow_execution_id ? (
        <>
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          <Link href={`/workflows/${workflowId}`}>Workflow Details</Link>
          <Icon icon={ArrowRightIcon} color="gray" size="xs" /> Workflow
          Execution Details
        </>
      ) : (
        <>
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          <Link href={`/workflows/${workflowId}`}>Workflow Details</Link>
        </>
      )}
      {clientParams.revision && (
        <>
          <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
          <Link
            href={`/workflows/${workflowId}/versions/${clientParams.revision}`}
          >
            Workflow Revision {clientParams.revision}
          </Link>
        </>
      )}
    </Subtitle>
  );
}
