"use client";
import { useEffect, useState } from "react";
import Loading from "@/app/(keep)/loading";
import { WorkflowBuilderPageClient } from "../../builder/page.client";
import { Subtitle } from "@tremor/react";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import { Icon } from "@tremor/react";
import { Link } from "@/components/ui";

export default function PageWithId({
  params,
}: {
  params: { workflowId: string };
}) {
  const [workflowPreviewData, setWorkflowPreviewData] = useState<any>(null);
  const key = params?.workflowId;

  useEffect(() => {
    if (key) {
      const data = localStorage.getItem("preview_workflow");
      if (data) {
        setWorkflowPreviewData(JSON.parse(data));
      }
    } else {
      setWorkflowPreviewData({});
    }
  }, [key]);

  return (
    <div className="flex flex-col mb-4 h-full gap-6">
      <Subtitle className="text-sm">
        <Link href="/workflows">All Workflows</Link>{" "}
        <Icon icon={ArrowRightIcon} color="gray" size="xs" /> Preview workflow
        template
      </Subtitle>
      <div className="flex-1 h-full">
        {!workflowPreviewData && <Loading />}
        {workflowPreviewData && workflowPreviewData.name === key && (
          <WorkflowBuilderPageClient
            workflowRaw={workflowPreviewData.workflow_raw || ""}
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
              <div className="text-center text-red-500">
                Workflow not found!
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
