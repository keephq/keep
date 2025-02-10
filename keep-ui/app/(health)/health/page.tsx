"use client";

import ProvidersTiles from "@/app/(keep)/providers/providers-tiles";
import React, { useEffect, useState } from "react";
import { defaultProvider, Provider } from "@/app/(keep)/providers/providers";
import { useProvidersWithHealthCheck } from "@/utils/hooks/useProviders";
import Loading from "@/app/(keep)/loading";

const useFetchProviders = () => {
  const [providers, setProviders] = useState<Provider[]>([]);
  const { data, error, mutate } = useProvidersWithHealthCheck();

  if (error) {
    throw error;
  }

  const isLocalhost: boolean = true;

  useEffect(() => {
    if (data) {
      const fetchedProviders = data.providers
        .filter((provider: Provider) => {
          return provider.health;
        })
        .map((provider) => ({
          ...defaultProvider,
          ...provider,
          id: provider.type,
          installed: provider.installed ?? false,
          health: provider.health,
        }));

      setProviders(fetchedProviders);
    }
  }, [data]);

  return {
    providers,
    error,
    isLocalhost,
    mutate,
  };
};

export default function ProviderHealthPage() {
  const { providers, isLocalhost, mutate } = useFetchProviders();

  if (!providers || providers.length <= 0) {
    return <Loading />;
  }

  return (
    <>
      <ProvidersTiles
        providers={providers}
        isLocalhost={isLocalhost}
        isHealthCheck={true}
        mutate={mutate}
      />
    </>
  );
}
