"use client";
import { defaultProvider, Provider } from "./providers";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { KeepApiError } from "@/shared/lib/KeepApiError";
import { useApiUrl } from "utils/hooks/useConfig";
import ProvidersTiles from "./providers-tiles";
import React, { useState, useEffect } from "react";
import Loading from "../loading";
import { useFilterContext } from "./filter-context";
import { toast } from "react-toastify";
import { useRouter } from "next/navigation";
import { useProviders } from "@/utils/hooks/useProviders";

export const useFetchProviders = () => {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [installedProviders, setInstalledProviders] = useState<Provider[]>([]);
  const [linkedProviders, setLinkedProviders] = useState<Provider[]>([]); // Added state for linkedProviders
  const { data: session, status } = useSession();

  const { data, error } = useProviders();

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
    if (data) {
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
  }, [data]);

  return {
    providers,
    installedProviders,
    linkedProviders, // Include linkedProviders in the returned object
    setInstalledProviders,
    status,
    error,
    session,
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
    isLocalhost,
  } = useFetchProviders();
  const { providersSearchString, providersSelectedTags } = useFilterContext();
  const apiUrl = useApiUrl();
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
  if (error) {
    throw new KeepApiError(
      error.message,
      `${apiUrl}/providers`,
      error.proposedResolution,
      error.statusCode
    );
  }
  if (status === "loading") return <Loading />;
  if (status === "unauthenticated") {
    router.push("/signin");
  }
  if (!providers || !installedProviders || providers.length <= 0)
    return <Loading />;

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
          installedProvidersMode={true}
        />
      )}
      {linkedProviders?.length > 0 && (
        <ProvidersTiles
          providers={linkedProviders}
          linkedProvidersMode={true}
          isLocalhost={isLocalhost}
        />
      )}
      <ProvidersTiles
        providers={providers.filter(
          (provider) => searchProviders(provider) && searchTags(provider)
        )}
        isLocalhost={isLocalhost}
      />
    </>
  );
}
