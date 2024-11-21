import { auth } from "@/auth";
import { getApiURL } from "utils/apiUrl";
import PageClient from "../page.client";

export default async function PageWithId({
  params,
}: {
  params: { workflowId: string };
}) {
  const accessToken = await auth();
  // server so we can use getApiUrl
  const apiUrl = getApiURL();
  const response = await fetch(`${apiUrl}/workflows/${params.workflowId}/raw`, {
    headers: {
      Authorization: `Bearer ${accessToken?.accessToken}`,
    },
    cache: "no-store",
  });
  const text = await response.json();
  return (
    <PageClient workflow={text.workflow_raw} workflowId={params.workflowId} />
  );
}
