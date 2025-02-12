"use client";
import { useEffect, useState } from "react";
import { KeepLoader } from "@/shared/ui";
import { WorkflowBuilderPageClient } from "../builder/page.client";
import Link from "next/link";

type PageProps = {
  params: { workflowId: string };
  searchParams: { [key: string]: string | undefined };
};

export default function Page({ params, searchParams }: PageProps) {
  const [workflowPreviewData, setWorkflowPreviewData] = useState<any>(null);
  const key = params.workflowId || searchParams.workflowId;

  useEffect(() => {
    if (key) {
      const data = localStorage.getItem("preview_workflow");
      if (data) {
        setWorkflowPreviewData(JSON.parse(data) || {});
      }
    } else {
      setWorkflowPreviewData({});
    }
  }, [params.workflowId, searchParams.workflowId]);

  return (
    <>
      {!workflowPreviewData && <KeepLoader />}
      {workflowPreviewData && workflowPreviewData.name === key && (
        <WorkflowBuilderPageClient
          workflowRaw={workflowPreviewData?.Workflow_raw}
          workflowId={params?.workflowId}
        />
      )}
      {workflowPreviewData && workflowPreviewData.name !== key && (
        <>
          <Link
            className="p-2 bg-orange-500 text-white hover:bg-orange-600 rounded"
            href="/workflows"
          >
            Go Back
          </Link>
          <div className="flex items-center justify-center min-h-screen">
            <div className="text-center text-red-500">Workflow not found!</div>
          </div>
        </>
      )}
    </>
  );
}
