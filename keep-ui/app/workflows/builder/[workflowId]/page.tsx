import { getServerSession } from "utils/customAuth";
import Page from "../page";
import { authOptions } from "pages/api/auth/[...nextauth]";
import { getApiURL } from "utils/apiUrl";
import { load, JSON_SCHEMA } from "js-yaml";

export default async function PageWithId({
  params,
}: {
  params: { workflowId: string };
}) {
  const accessToken = await getServerSession(authOptions);
  const apiUrl = getApiURL();
  const response = await fetch(`${apiUrl}/workflows/${params.workflowId}/raw`, {
    headers: {
      Authorization: `Bearer ${accessToken?.accessToken}`,
    },
    cache: "no-store",
  });
  const text = await response.json();
  return <Page workflow={text.workflow_raw} workflowId={params.workflowId} />;
}
