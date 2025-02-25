"use client";
import { defaultProvider, Provider } from "@/shared/api/providers";
import ProvidersTiles from "./providers-tiles";
import React, { useState, useEffect } from "react";
import Loading from "@/app/(keep)/loading";
import { useFilterContext } from "./filter-context";
import { toast } from "react-toastify";
import { useProviders } from "@/utils/hooks/useProviders";
import { showErrorToast } from "@/shared/ui";
import { Link } from "@/components/ui";
import { useConfig } from "@/utils/hooks/useConfig";

export const useFetchProviders = () => {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [installedProviders, setInstalledProviders] = useState<Provider[]>([]);
  const [linkedProviders, setLinkedProviders] = useState<Provider[]>([]); // Added state for linkedProviders
  const { data: config } = useConfig();
  const { data, error, mutate } = useProviders();

  if (error) {
    throw error;
  }

  const isLocalhost = data && data.is_localhost;
  const toastShownKey = "localhostToastShown";
  const ToastMessage = () => (
    <div>
      Webhooks are disabled because Keep is not accessible from the internet.
      <br />
      <Link
        href={`${
          config?.KEEP_DOCS_URL || "https://docs.keephq.dev"
        }/development/external-url`}
        target="_blank"
        rel="noreferrer noopener"
      >
        Read docs
      </Link>{" "}
      to learn how to enable it.
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
            `${config?.KEEP_DOCS_URL || "https://docs.keephq.dev"}`,
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
    error,
    isLocalhost,
    mutate,
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
    isLocalhost,
    mutate,
  } = useFetchProviders();

  const {
    providersSearchString,
    providersSelectedTags,
    providersSelectedCategories,
  } = useFilterContext();

  useEffect(() => {
    if (searchParams?.oauth === "failure") {
      const reason = JSON.parse(searchParams.reason);
      showErrorToast(new Error(`Failed to install provider: ${reason.detail}`));
    } else if (searchParams?.oauth === "success") {
      toast.success("Successfully installed provider", {
        position: toast.POSITION.TOP_LEFT,
      });
    }
  }, [searchParams]);

  if (!providers || !installedProviders || providers.length <= 0) {
    // TODO: skeleton loader
    return <Loading />;
  }

  const searchProviders = (provider: Provider) => {
    return (
      !providersSearchString ||
      provider.type?.toLowerCase().includes(providersSearchString.toLowerCase())
    );
  };

  const searchCategories = (provider: Provider) => {
    if (providersSelectedCategories.includes("Coming Soon")) {
      if (provider.coming_soon) {
        return true;
      }
    }

    return (
      providersSelectedCategories.length === 0 ||
      provider.categories.some((category) =>
        providersSelectedCategories.includes(category)
      )
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
          mutate={mutate}
        />
      )}
      {linkedProviders?.length > 0 && (
        <ProvidersTiles
          providers={linkedProviders}
          linkedProvidersMode={true}
          isLocalhost={isLocalhost}
          mutate={mutate}
        />
      )}
      <ProvidersTiles
        providers={providers.filter(
          (provider) =>
            searchProviders(provider) &&
            searchTags(provider) &&
            searchCategories(provider)
        )}
        isLocalhost={isLocalhost}
        mutate={mutate}
      />
    </>
  );
}
