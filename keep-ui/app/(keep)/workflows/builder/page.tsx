import { WorkflowBuilderWidget } from "@/widgets/workflow-builder";
import { Metadata } from "next";

type PageProps = {
  params: Promise<{ workflow: string; workflowId: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export default async function WorkflowBuilderPage(props: PageProps) {
  const params = await props.params;
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
