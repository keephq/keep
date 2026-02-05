import { getWorkflowWithRedirectSafe } from "@/shared/api/workflows";

export async function GET(
  request: Request,
  props: { params: Promise<{ workflow_filename: string }> }
) {
  const params = await props.params;
  const { workflow_filename } = params;
  const workflow_id = workflow_filename.replace(".yaml", "");
  const workflow = await getWorkflowWithRedirectSafe(workflow_id);
  if (!workflow) {
    return new Response("Workflow not found", { status: 404 });
  }
  return new Response(workflow.workflow_raw, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}
