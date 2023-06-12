'use client';
import { Card, Title, Text } from "@tremor/react";
import ProvidersTable from "./table";
import ProvidersConnect from "./providers-connect";
import { Providers, defaultProvider, Provider } from "./providers";
import { getServerSession, useSession } from "../../utils/customAuth";
import { getApiURL } from "../../utils/apiUrl";


export default async function ProvidersPage() {
  console.log("Rendering providers page");
  //const session = await getServerSession(authOptions);
  const { data: session, status, update } = useSession();
  if (status === "loading"){
    console.log("Loading session");
    return <div>Loading...</div>;
  }
  if (status === "unauthenticated") {
    console.log("Unauthenticated");
    return <div>Unauthenticated...</div>;
  }
  // force get session to get a token
  const accessToken = session?.accessToken;

  let providers= [];
  let installedProviders = [];
  // Now let's fetch the providers status from the backend
  try {
    const apiUrl = getApiURL();
    const response = await fetch(`${apiUrl}/providers`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    })
    if (response.ok) {
      const responseJson = await response.json();
      installedProviders=responseJson["installed_providers"];
      providers = responseJson.providers.map((provider: Provider) => {
          const updatedProvider: Provider = {
            config: { ...defaultProvider.config, ...(provider as Provider).config },
            installed: (provider as Provider).installed ?? defaultProvider.installed,
            details: {
              authentication: {
                ...defaultProvider.details.authentication,
                ...((provider as Provider).details?.authentication || {}),
              },
            },
            id: provider.type,
            comingSoon: (provider as Provider).comingSoon || defaultProvider.comingSoon,
            can_query: false,
            can_notify: false,
            type: provider.type,
          };
          return updatedProvider;
        }) as Providers;


    } else {
      throw new Error("Failed to fetch providers status");
    }
  } catch (err) {
    console.log("Error fetching providers status", err);
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
        <ProvidersConnect session={session} providers={providers} />
      </Card>
      <Title>Installed Providers</Title>
      <Card className="mt-6">
        <ProvidersTable session={session} providers={installedProviders} />
      </Card>
    </main>
  );
}
