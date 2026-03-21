"use client";
import { useI18n } from "@/i18n/hooks/useI18n";
import { useEffect, useState, use } from "react";
import { KeepLoader } from "@/shared/ui";
import { WorkflowBuilderWidget } from "@/widgets/workflow-builder";
import Link from "next/link";

type PageProps = {
  params: Promise<{ workflowId: string }>;
  searchParams: Promise<{ [key: string]: string | undefined }>;
};

export default function Page(props: PageProps) {
  const { t } = useI18n();
  const searchParams = use(props.searchParams);
  const params = use(props.params);
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
      {!workflowPreviewData && (
        <KeepLoader loadingText={t("workflows.preview.loading")} />
      )}
      {workflowPreviewData && workflowPreviewData.name === key && (
        <WorkflowBuilderWidget
          workflowRaw={workflowPreviewData?.Workflow_raw}
          workflowId={params?.workflowId}
          standalone={true}
        />
      )}
      {workflowPreviewData && workflowPreviewData.name !== key && (
        <>
          <Link
            className="p-2 bg-orange-500 text-white hover:bg-orange-600 rounded"
            href="/workflows"
          >
            {t("common.actions.goBack")}
          </Link>
          <div className="flex items-center justify-center min-h-screen">
            <div className="text-center text-red-500">{t("workflows.preview.notFound")}</div>
          </div>
        </>
      )}
    </>
  );
}
