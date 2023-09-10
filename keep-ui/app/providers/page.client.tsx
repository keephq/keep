"use client";
import { Providers, defaultProvider, Provider } from "./providers";
import { useSession } from "../../utils/customAuth";
import { getApiURL } from "../../utils/apiUrl";
import { fetcher } from "../../utils/fetcher";
import { KeepApiError } from "../error";
import ProvidersAvailable from "./providers-available";
import React, { useState, Suspense } from "react";
import useSWR from "swr";
import Loading from "../loading";
import Image from "next/image";
import ProvidersInstalled from "./providers-installed";

export const useFetchProviders = () => {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [installedProviders, setInstalledProviders] = useState<Provider[]>([]);
  const { data: session, status } = useSession();
  let shouldFetch = session?.accessToken ? true : false;

  const { data, error } = useSWR(
    shouldFetch ? `${getApiURL()}/providers` : null,
    (url) => {
      return fetcher(url, session?.accessToken!);
    }
  );

  // process data here if it's available
  if (data && providers.length === 0 && installedProviders.length === 0) {
    // TODO: need to refactor the backend response
    const fetchedInstalledProviders = (
      data["installed_providers"] as Providers
    ).map((provider) => {
      return { ...provider, installed: true } as Provider;
    });
    // TODO: refactor this to be more readable and move to backend(?)
    const fetchedProviders = data.providers.map((provider: Provider) => {
      const updatedProvider: Provider = {
        config: { ...defaultProvider.config, ...(provider as Provider).config },
        installed: (provider as Provider).installed ?? false,
        details: {
          authentication: {
            ...defaultProvider.details.authentication,
            ...((provider as Provider).details?.authentication || {}),
          },
        },
        id: provider.type,
        comingSoon:
          (provider as Provider).comingSoon || defaultProvider.comingSoon,
        can_query: false,
        can_notify: false,
        type: provider.type,
        can_setup_webhook: provider.can_setup_webhook,
        supports_webhook: provider.supports_webhook,
        provider_description: provider.provider_description,
      };
      return updatedProvider;
    }) as Providers;

    setInstalledProviders(fetchedInstalledProviders);
    setProviders(fetchedProviders);
  }
  return {
    providers,
    installedProviders,
    setInstalledProviders,
    status,
    error,
  };
};

export default function ProvidersPage() {
  const {
    providers,
    installedProviders,
    setInstalledProviders,
    status,
    error,
  } = useFetchProviders();

  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") return <div>Unauthenticated</div>;
  if (!providers || !installedProviders) return <Loading />;
  if (error) throw new KeepApiError(error.message, `${getApiURL()}/providers`);

  const addProvider = (provider: Provider) => {
    setInstalledProviders((prevProviders) => [
      ...prevProviders,
      { ...provider, installed: true } as Provider,
    ]);
  };

  const deleteProvider = (provider: Provider) => {
    setInstalledProviders((prevProviders) =>
      prevProviders.filter((p) => p.id !== provider.id)
    );
  };

  return (
    <Suspense
      fallback={
        <Image src="/keep.gif" width={200} height={200} alt="Loading" />
      }
    >
      <ProvidersInstalled
        providers={installedProviders}
        onDelete={deleteProvider}
      />
      <ProvidersAvailable providers={providers} addProvider={addProvider} />
    </Suspense>
  );
}
