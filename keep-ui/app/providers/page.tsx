import { Card, Title, Text } from "@tremor/react";
import ProvidersTable from "./table";
import { getServerSession } from "../../utils/customAuth";
import { getApiURL } from "../../utils/apiUrl";
import { authOptions } from "../../pages/api/auth/[...nextauth]";

export default async function ProvidersPage() {
  const session = await getServerSession(authOptions);
  // force get session to get a token
  const accessToken = session?.accessToken;
  let installedProviders = [];
  // Now let's fetch the providers status from the backend
  try {
    const apiUrl = getApiURL();
    installedProviders = await fetch(`${apiUrl}/providers`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    }).then((res) => res.json());
  } catch (err) {
    if (err instanceof Error) {
      return <div>Error: {err.message}</div>;
    }
    return <div>502 backend error</div>;
  }

  return (
    <main className="p-4 md:p-10 mx-auto max-w-7xl">
      <Title>Providers</Title>
      <Text>Connect providers to Keep to make your alerts better.</Text>
      <Card className="mt-6">
        <ProvidersTable session={session} installedProviders={installedProviders} />
      </Card>
    </main>
  );
}
