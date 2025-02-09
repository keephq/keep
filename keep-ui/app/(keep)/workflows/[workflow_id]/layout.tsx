import { getWorkflowWithRedirectSafe } from "@/shared/api/workflows";
import { WorkflowBreadcrumbs } from "./workflow-breadcrumbs";
import WorkflowDetailHeader from "./workflow-detail-header";
import { WorkflowBuilderProvider } from "../builder/workflow-builder-context";

export default async function Layout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { workflow_id: string };
}) {
  const workflow = await getWorkflowWithRedirectSafe(params.workflow_id);
  return (
    <WorkflowBuilderProvider workflowId={params.workflow_id}>
      <div className="flex flex-col mb-4 h-full gap-6">
        <WorkflowBreadcrumbs workflowId={params.workflow_id} />
        <WorkflowDetailHeader
          workflowId={params.workflow_id}
          initialData={workflow}
        />
        <div className="flex-1 h-full">{children}</div>
      </div>
    </WorkflowBuilderProvider>
  );
}
