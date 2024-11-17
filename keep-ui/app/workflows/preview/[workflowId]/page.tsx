"use client";
import { useEffect, useState, use } from "react";
import PageClient from "../../builder/page.client";
import Loading from "../../../loading";
import Link from "next/link";

export default function PageWithId(
  props: {
    params: Promise<{ workflowId: string }>;
  }
) {
  const params = use(props.params);
  const [workflowPreviewData, setWorkflowPreviewData] = useState<any>(null);
  const key = params?.workflowId;

  useEffect(() => {
    if (key) {
      const data = localStorage.getItem("preview_workflow");
      if (data) {
        setWorkflowPreviewData(JSON.parse(data));
      }
    } else {
      workflowPreviewData({});
    }
  }, [params.workflowId]);

  return (
    <>
      {!workflowPreviewData && <Loading />}
      {workflowPreviewData && workflowPreviewData.name === key && (
        <PageClient
          workflow={workflowPreviewData.workflow_raw || ""}
          isPreview={true}
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
