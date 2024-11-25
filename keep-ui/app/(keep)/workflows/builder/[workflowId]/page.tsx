import PageClient from "../page.client";
import { getServerApiClient } from "@/shared/lib/api/getServerApiClient";

export default async function PageWithId({
  params,
}: {
  params: { workflowId: string };
}) {
  const api = await getServerApiClient();
  const text = await api.get(`/workflows/${params.workflowId}/raw`, {
    cache: "no-store",
  });
  return (
    <PageClient workflow={text.workflow_raw} workflowId={params.workflowId} />
  );
}
