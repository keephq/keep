import { WorkflowBuilderPageClient } from "./page.client";
import { Suspense } from "react";
import Loading from "@/app/(keep)/loading";
import { Metadata } from "next";

type PageProps = {
  params: { workflow: string; workflowId: string };
  searchParams: { [key: string]: string | string[] | undefined };
};

export default function WorkflowBuilderPage({
  params,
  searchParams,
}: PageProps) {
  return (
    <Suspense fallback={<Loading />}>
      <WorkflowBuilderPageClient
        workflowRaw={params.workflow}
        workflowId={params.workflowId}
      />
    </Suspense>
  );
}

export const metadata: Metadata = {
  title: "Keep - Workflow Builder",
  description: "Build workflows with a UI builder.",
};
