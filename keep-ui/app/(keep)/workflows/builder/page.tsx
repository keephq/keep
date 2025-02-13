import { WorkflowBuilderWidget } from "@/widgets/workflow-builder";
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
    <WorkflowBuilderWidget
      workflowRaw={params.workflow}
      workflowId={params.workflowId}
      standalone={true}
    />
  );
}

export const metadata: Metadata = {
  title: "Keep - Workflow Builder",
  description: "Build workflows with a UI builder.",
};
