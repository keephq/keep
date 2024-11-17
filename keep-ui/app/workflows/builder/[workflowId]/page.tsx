import { getServerSession } from "next-auth/next";
import { authOptions } from "pages/api/auth/[...nextauth]";
import { getApiURL } from "utils/apiUrl";
import PageClient from "../page.client";

export default async function PageWithId(
  props: {
    params: Promise<{ workflowId: string }>;
  }
) {
  const params = await props.params;
  const accessToken = await getServerSession(authOptions);
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
