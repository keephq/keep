import { Card, Title, Text } from "@tremor/react";
import ProvidersTable from "./table";
import ProvidersConnect from "./providers-connect";
import { Providers, defaultProvider, Provider } from "./providers";
import { getServerSession } from "../../utils/customAuth";
import { getApiURL } from "../../utils/apiUrl";
import { authOptions } from "../../pages/api/auth/[...nextauth]";

export default async function ProvidersPage() {
  const session = await getServerSession(authOptions);
  // force get session to get a token
  const accessToken = session?.accessToken;
  let providers = {};
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
      providers = Object.fromEntries(
        Object.entries(responseJson).map(([providerName, provider]) => {
          const updatedProvider: Provider = {
            config: { ...defaultProvider.config, ...(provider as Provider).config },
            installed: (provider as Provider).installed ?? defaultProvider.installed,
            details: {
              authentication: {
                ...defaultProvider.details.authentication,
                ...((provider as Provider).details?.authentication || {}),
              },
            },
            id: providerName.split('_')[0],
            comingSoon: (provider as Provider).comingSoon || defaultProvider.comingSoon,
          };
          return [providerName, updatedProvider];
        })
      ) as Providers;
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

  const connectedProviders = Object.fromEntries(
    Object.entries(providers).filter(([_, provider]) => (provider as Provider).installed)
  ) as Providers;


  return (
    <main className="p-4 md:p-10 mx-auto max-w-7xl">
      <Title>Providers</Title>
      <Text>Connect providers to Keep to make your alerts better.</Text>
      <Card className="mt-6">
        <ProvidersConnect session={session} providers={providers} />
      </Card>
      <Text>Connected Providers</Text>
      <Card className="mt-6">
        <ProvidersTable session={session} providers={connectedProviders} />
      </Card>
    </main>
  );
}
