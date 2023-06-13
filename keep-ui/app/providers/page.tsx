'use client';
import { Card, Title, Text } from "@tremor/react";
import ProvidersTable from "./table";
import ProvidersConnect from "./providers-connect";
import { Providers, defaultProvider, Provider } from "./providers";
// import { getServerSession  } from "../../utils/customAuth";
import { useSession  } from "../../utils/customAuth";
import { getApiURL } from "../../utils/apiUrl";
import React, { useState, useEffect } from 'react';


export default function ProvidersPage() {
  console.log("Rendering providers page");
  const [installedProviders, setInstalledProviders] = useState<Provider[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const { data: session, status, update } = useSession();
  // force get session to get a token
  const accessToken = session?.accessToken;

  const fetchProviders = async () => {
    try {
      const apiUrl = getApiURL();
      const response = await fetch(`${apiUrl}/providers`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (response.ok) {
        const responseJson = await response.json();
        const installedProviders = responseJson["installed_providers"] as Providers;
        const providers = responseJson.providers.map((provider: Provider) => {
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

        return { installedProviders, providers };
      } else {
        throw new Error("Failed to fetch providers status");
      }
    } catch (err) {
      console.log("Error fetching providers status", err);
      // You might want to handle the error differently here, for example by throwing the error
      // and catching it in the useEffect where you call this function.
      throw err;
    }
  };


  useEffect(() => {
    fetchProviders().then(({ installedProviders, providers }) => {
      setInstalledProviders(installedProviders);
      setProviders(providers);
    }).catch(err => {
        console.log("Error fetching providers", err);
    });
  }, []);


  const addProvider = (provider: Provider) => {
      setInstalledProviders(prevProviders => [...prevProviders, provider]);
  };

  if (status === "loading") {
    console.log("Loading...")
    return <div>Loading...</div>;
  }
  if (status === "unauthenticated"){
    console.log("Unauthenticated...")
    return <div>Unauthenticated...</div>;
  }

  return (
    <main className="p-4 md:p-10 mx-auto max-w-7xl">
      <Title>Providers</Title>
      <Text>Connect providers to Keep to make your alerts better.</Text>
      <Card className="mt-6">
        <ProvidersConnect providers={providers} addProvider={addProvider}/>
      </Card>
      <Title>Installed Providers</Title>
      <Card className="mt-6">
        <ProvidersTable providers={installedProviders} />
      </Card>
    </main>
  );
}
