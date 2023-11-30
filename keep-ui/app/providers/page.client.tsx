"use client";
import {
  Providers,
  defaultProvider,
  Provider,
  ProvidersResponse,
} from "./providers";
import { useSession } from "next-auth/react";
import { getApiURL } from "../../utils/apiUrl";
import { fetcher } from "../../utils/fetcher";
import { KeepApiError } from "../error";
import ProvidersTiles from "./providers-tiles";
import React, { useState, Suspense, useContext, useEffect } from "react";
import useSWR from "swr";
import Loading from "../loading";
import { LayoutContext } from "./context";
import { toast } from "react-toastify";
import { updateIntercom } from "@/components/ui/Intercom";
import { useRouter } from "next/navigation";
import { Callout } from "@tremor/react";

export const useFetchProviders = () => {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [installedProviders, setInstalledProviders] = useState<Provider[]>([]);
  const [isSlowLoading, setIsSlowLoading] = useState<boolean>(false);
  const { data: session, status } = useSession();
  let shouldFetch = session?.accessToken ? true : false;


  const { data, error } = useSWR<ProvidersResponse>(
    shouldFetch ? `${getApiURL()}/providers` : null,
    (url) => {
      return fetcher(url, session?.accessToken!);
    },
    {
      onLoadingSlow: () => setIsSlowLoading(true),
      loadingTimeout: 5000,
      revalidateOnFocus: false,
    }
  );

  const isLocalhost = data && data.is_localhost;
  const toastShownKey = 'localhostToastShown';
  const ToastMessage = () => (
    <div>
      Webhooks are disabled because Keep is not accessible from the internet.<br /><br />

      Click for Keep docs on how to enabled it 📚
    </div>
  );

  useEffect(() => {
    const toastShown = localStorage.getItem(toastShownKey);

    if (isLocalhost && !toastShown) {
      toast(<ToastMessage/>, {
        type: "info",
        position: toast.POSITION.TOP_CENTER,
        autoClose: 10000,
        onClick: () => window.open('https://docs.keephq.dev/development/external-url', '_blank'),
        style: {
          width: "250%", // Set width
          marginLeft: "-75%", // Adjust starting position to left
        },
        progressStyle: { backgroundColor: 'orange' }
      });
      localStorage.setItem(toastShownKey, 'true');
    }
  }, [isLocalhost]);

  // process data here if it's available
  if (data && providers.length === 0 && installedProviders.length === 0) {
    // TODO: need to refactor the backend response
    const fetchedInstalledProviders = data.installed_providers.map(
      (provider) => {
        const validatedScopes = provider.validatedScopes ?? {};
        return {
          ...provider,
          installed: true,
          validatedScopes: validatedScopes,
        } as Provider;
      }
    );
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
        oauth2_url: provider.oauth2_url,
        scopes: provider.scopes,
        validatedScopes: provider.validatedScopes,
        tags: provider.tags,
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
    session,
    isSlowLoading,
    isLocalhost
  };
};

export default function ProvidersPage({
  searchParams,
}: {
  searchParams?: { [key: string]: string };
}) {
  const {
    providers,
    installedProviders,
    setInstalledProviders,
    status,
    error,
    session,
    isSlowLoading,
    isLocalhost
  } = useFetchProviders();
  const { searchProviderString, selectedTags } = useContext(LayoutContext);
  const router = useRouter();
  useEffect(() => {
    if (searchParams?.oauth === "failure") {
      const reason = JSON.parse(searchParams.reason);
      toast.error(`Failed to install provider: ${reason.detail}`, {
        position: toast.POSITION.TOP_LEFT,
      });
    } else if (searchParams?.oauth === "success") {
      toast.success("Successfully installed provider", {
        position: toast.POSITION.TOP_LEFT,
      });
    }
  }, [searchParams]);
  useEffect(() => {
    updateIntercom(session?.user);
  }, [session?.user]);

  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") router.push("/signin");
  if (!providers || !installedProviders || providers.length <= 0)
    return <Loading slowLoading={isSlowLoading} />;
  if (error) {
    throw new KeepApiError(error.message, `${getApiURL()}/providers`);
  }

  const addProvider = (provider: Provider) => {
    setInstalledProviders((prevProviders) => {
      const existingProvider = prevProviders.findIndex(
        (p) => p.id === provider.id
      );
      if (existingProvider > -1) {
        prevProviders.splice(existingProvider, 1);
      }
      return [...prevProviders, { ...provider, installed: true } as Provider];
    });
  };

  const deleteProvider = (provider: Provider) => {
    setInstalledProviders((prevProviders) =>
      prevProviders.filter((p) => p.id !== provider.id)
    );
  };

  const searchProviders = (provider: Provider) => {
    return (
      !searchProviderString ||
      provider.type?.toLowerCase().includes(searchProviderString.toLowerCase())
    );
  };

  const searchTags = (provider: Provider) => {
    return (
      selectedTags.length === 0 ||
      provider.tags.some((tag) => selectedTags.includes(tag))
    );
  };

  return (
    <>
      {installedProviders.length > 0 && (
        <ProvidersTiles
          providers={installedProviders}
          addProvider={addProvider}
          onDelete={deleteProvider}
          installedProvidersMode={true}
        />
      )}
      <ProvidersTiles
        providers={providers.filter(
          (provider) => searchProviders(provider) && searchTags(provider)
        )}
        addProvider={addProvider}
        onDelete={deleteProvider}
        isLocalhost={isLocalhost}
      />
    </>
  );
}
