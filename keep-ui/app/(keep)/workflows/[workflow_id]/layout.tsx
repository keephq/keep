"use client";

import { Link } from "@/components/ui";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import { Icon, Subtitle } from "@tremor/react";
import { useParams } from "next/navigation";
import WorkflowDetailHeader from "./workflow-detail-header";

export default function Layout({
  children,
  params,
}: {
  children: any;
  params: { workflow_id: string };
}) {
  const clientParams = useParams();
  return (
    <div className="flex flex-col mb-4 h-full gap-6">
      <Subtitle className="text-sm">
        <Link href="/workflows">All Workflows</Link>{" "}
        <Icon icon={ArrowRightIcon} color="gray" size="xs" />{" "}
        {clientParams.workflow_execution_id ? (
          <>
            <Link href={`/workflows/${params.workflow_id}`}>
              Workflow Details
            </Link>
            <Icon icon={ArrowRightIcon} color="gray" size="xs" /> Workflow
            Execution Details
          </>
        ) : (
          "Workflow Details"
        )}
      </Subtitle>
      <WorkflowDetailHeader workflow_id={params.workflow_id} />
      <div className="flex-1 h-full">{children}</div>
    </div>
  );
}
