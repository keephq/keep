"use client";
import {
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
import { useFilterContext } from "./filter-context";
import { toast } from "react-toastify";
import { useRouter } from "next/navigation";

export const useFetchProviders = () => {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [installedProviders, setInstalledProviders] = useState<Provider[]>([]);
  const [linkedProviders, setLinkedProviders] = useState<Provider[]>([]); // Added state for linkedProviders
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
  const toastShownKey = "localhostToastShown";
  const ToastMessage = () => (
    <div>
      Webhooks are disabled because Keep is not accessible from the internet.
      <br />
      <br />
      Click for Keep docs on how to enabled it 📚
    </div>
  );

  useEffect(() => {
    const toastShown = localStorage.getItem(toastShownKey);

    if (isLocalhost && !toastShown) {
      toast(<ToastMessage />, {
        type: "info",
        position: toast.POSITION.TOP_CENTER,
        autoClose: 10000,
        onClick: () =>
          window.open(
            "https://docs.keephq.dev/development/external-url",
            "_blank"
          ),
        style: {
          width: "250%", // Set width
          marginLeft: "-75%", // Adjust starting position to left
        },
        progressStyle: { backgroundColor: "orange" },
      });
      localStorage.setItem(toastShownKey, "true");
    }
  }, [isLocalhost]);

  useEffect(() => {
    if (
      data &&
      providers.length === 0 &&
      installedProviders.length === 0 &&
      linkedProviders.length === 0
    ) {
      const fetchedInstalledProviders = data.installed_providers.map(
        (provider) => ({
          ...provider,
          installed: true,
          validatedScopes: provider.validatedScopes ?? {},
        })
      );

      const fetchedProviders = data.providers.map((provider) => ({
        ...defaultProvider,
        ...provider,
        id: provider.type,
        installed: provider.installed ?? false,
      }));

      const fetchedLinkedProviders = data.linked_providers?.map((provider) => ({
        ...defaultProvider,
        ...provider,
        linked: true,
        validatedScopes: provider.validatedScopes ?? {},
      }));

      setInstalledProviders(fetchedInstalledProviders);
      setProviders(fetchedProviders);
      setLinkedProviders(fetchedLinkedProviders); // Update state with linked providers
    }
  }, [
    data,
    providers.length,
    installedProviders.length,
    linkedProviders?.length,
  ]);

  return {
    providers,
    installedProviders,
    linkedProviders, // Include linkedProviders in the returned object
    setInstalledProviders,
    status,
    error,
    session,
    isSlowLoading,
    isLocalhost,
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
    linkedProviders,
    setInstalledProviders,
    status,
    error,
    session,
    isSlowLoading,
    isLocalhost,
  } = useFetchProviders();
  const { providersSearchString, providersSelectedTags } = useFilterContext();
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
      !providersSearchString ||
      provider.type?.toLowerCase().includes(providersSearchString.toLowerCase())
    );
  };

  const searchTags = (provider: Provider) => {
    return (
      providersSelectedTags.length === 0 ||
      provider.tags.some((tag) => providersSelectedTags.includes(tag))
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
      {linkedProviders?.length > 0 && (
        <ProvidersTiles
          providers={linkedProviders}
          addProvider={addProvider}
          onDelete={deleteProvider}
          linkedProvidersMode={true}
          isLocalhost={isLocalhost}
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
