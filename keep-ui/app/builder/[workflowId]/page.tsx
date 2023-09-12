import { getServerSession } from "utils/customAuth";
import Page from "../page";
import { authOptions } from "pages/api/auth/[...nextauth]";
import { getApiURL } from "utils/apiUrl";

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
  const workflow = (await response.text()).slice(1, -1).replaceAll("\\n", "\n");
  return <Page workflow={workflow} workflowId={params.workflowId} />;
}
