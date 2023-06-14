'use client';
import { Card, Title, Text } from "@tremor/react";
import ProvidersTable from "./table";
import ProvidersConnect from "./providers-connect";
import { Providers, defaultProvider, Provider } from "./providers";
import { useSession  } from "../../utils/customAuth";
import { getApiURL } from "../../utils/apiUrl";
import React, { useState, Suspense } from 'react';
import useSWR from "swr";
import Loading from '../loading'

const fetcher = async (url: string, accessToken: string) => {
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
  if (response.ok) {
    return response.json();
  }
  throw new Error("Failed to fetch providers status");
};

export default function ProvidersPage() {
  console.log("Rendering providers page");
  const { data: session, status, update } = useSession();
  const accessToken = session?.accessToken;

  const { data, error } = useSWR(() => accessToken ? `${getApiURL()}/providers` : null, (url) => fetcher(url, accessToken));

  const [providers, setProviders] = useState<Provider[]>([]);
  const [installedProviders, setInstalledProviders] = useState<Provider[]>([]);

  const addProvider = (provider: Provider) => {
    setInstalledProviders(prevProviders => [...prevProviders, provider]);
  };

  if (!data) return <div><Loading/></div>;  // Loading state
  if (error) return <div>Error: {error.message}</div>;  // Error state

  // process data here if it's available
  if (data && providers.length === 0 && installedProviders.length === 0) {
    const fetchedInstalledProviders = data["installed_providers"] as Providers;
    const fetchedProviders = data.providers.map((provider: Provider) => {
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

    setInstalledProviders(fetchedInstalledProviders);
    setProviders(fetchedProviders);
  }

  return (
    <main className="p-4 md:p-10 mx-auto max-w-7xl">
      <Title>Providers</Title>
      <Text>Connect providers to Keep to make your alerts better.</Text>
      <Card className="mt-6">

      <Suspense fallback={<img src='/keep.gif'/>}>
        <ProvidersConnect providers={providers} addProvider={addProvider}/>
      </Suspense>

      </Card>
      <Title>Installed Providers</Title>
      <Card className="mt-6">
        <ProvidersTable providers={installedProviders} />
      </Card>
    </main>
  );
}
