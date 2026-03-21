"use client";
import { useI18n } from "@/i18n/hooks/useI18n";
import { useEffect, useState, use } from "react";
import { KeepLoader } from "@/shared/ui";
import { WorkflowBuilderWidget } from "@/widgets/workflow-builder";
import { Subtitle } from "@tremor/react";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import { Icon } from "@tremor/react";
import { Link } from "@/components/ui";

export default function PageWithId(
  props: {
    params: Promise<{ workflowId: string }>;
  }
) {
  const { t } = useI18n();
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
      setWorkflowPreviewData({});
    }
  }, [key]);

  return (
    <div className="flex flex-col h-full gap-4">
      <Subtitle className="text-sm">
        <Link href="/workflows">{t("workflows.breadcrumbs.allWorkflows")}</Link>{" "}
        <Icon icon={ArrowRightIcon} color="gray" size="xs" /> {t("workflows.preview.title")}
      </Subtitle>
      <div className="flex-1 h-full">
        {!workflowPreviewData && (
          <KeepLoader loadingText={t("workflows.preview.loading")} />
        )}
        {workflowPreviewData && workflowPreviewData.name === key && (
          <WorkflowBuilderWidget
            workflowRaw={workflowPreviewData.workflow_raw || ""}
            workflowId={undefined}
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
              <div className="text-center text-red-500">
                {t("workflows.preview.notFound")}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
