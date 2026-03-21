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
import { useI18n } from "@/i18n/hooks/useI18n";

export const useFetchProviders = () => {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [installedProviders, setInstalledProviders] = useState<Provider[]>([]);
  const [linkedProviders, setLinkedProviders] = useState<Provider[]>([]);
  const { data: config } = useConfig();
  const { data, error, mutate, isLoading } = useProviders();

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
    // Check if we're in a browser environment before accessing localStorage
    if (typeof window === "undefined" || typeof localStorage === "undefined") {
      return;
    }
    
    const toastShown = localStorage.getItem(toastShownKey);

    if (isLocalhost && !toastShown) {
      toast(<ToastMessage />, {
        type: "info",
        position: "top-center",
        autoClose: 10000,
        onClick: () =>
          window.open(
            `${config?.KEEP_DOCS_URL || "https://docs.keephq.dev"}`,
            "_blank"
          ),
        style: {
          width: "250%",
          marginLeft: "-75%",
        },
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

      const fetchedLinkedProviders = (data.linked_providers ?? []).map(
        (provider, i) => ({
          ...defaultProvider,
          ...provider,
          id: provider.type + "-linked-" + i,
          linked: true,
          validatedScopes: provider.validatedScopes ?? {},
        })
      );

      setInstalledProviders(fetchedInstalledProviders);
      setProviders(fetchedProviders);
      setLinkedProviders(fetchedLinkedProviders);
    }
  }, [data]);

  return {
    providers,
    installedProviders,
    linkedProviders,
    setInstalledProviders,
    error,
    isLocalhost,
    mutate,
    isLoading,
  };
};

export default function ProvidersPage({
  searchParams,
}: {
  searchParams?: { [key: string]: string | string[] | undefined };
}) {
  const { t } = useI18n();
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

  const isFilteringActive =
    providersSearchString ||
    providersSelectedTags.length > 0 ||
    providersSelectedCategories.length > 0;

  useEffect(() => {
    if (searchParams?.oauth === "failure") {
      try {
        const reason = JSON.parse(searchParams.reason as string);
        showErrorToast(
          new Error(`Failed to install provider: ${reason.detail}`)
        );
      } catch (error) {
        showErrorToast(
          new Error(`Failed to install provider: ${searchParams.reason}`)
        );
      }
    } else if (searchParams?.oauth === "success") {
      toast.success(t("providers.messages.installSuccess"), {
        position: "top-left",
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

  const filteredProviders = providers.filter(
    (provider) =>
      searchProviders(provider) &&
      searchTags(provider) &&
      searchCategories(provider)
  );

  const displayableProviders = filteredProviders.filter(
    (provider) =>
      Object.keys(provider.config || {}).length > 0 ||
      (provider.tags && provider.tags.includes("alert"))
  );

  return (
    <>
      {isFilteringActive && (
        <div className="mb-4">
          <ProvidersTiles
            title={t("providers.available")}
            providers={filteredProviders}
            isLocalhost={isLocalhost}
            mutate={mutate}
          />
          {displayableProviders.length > 0 && (
            <p className="text-m text-gray-500">
              {displayableProviders.length} {t("providers.labels.provider")}
              {displayableProviders.length > 1 ? "s" : ""} {t("providers.messages.found")}
            </p>
          )}
          {displayableProviders.length === 0 && (
            <p className="text-m text-gray-500">
              {t("providers.messages.noProviders")}
            </p>
          )}
        </div>
      )}
      {installedProviders.length > 0 && (
        <ProvidersTiles
          title={t("providers.installed")}
          providers={installedProviders}
          installedProvidersMode={true}
          mutate={mutate}
        />
      )}
      {linkedProviders?.length > 0 && (
        <ProvidersTiles
          title={t("providers.linked")}
          providers={linkedProviders}
          linkedProvidersMode={true}
          isLocalhost={isLocalhost}
          mutate={mutate}
        />
      )}
      {!isFilteringActive && (
        <ProvidersTiles
          title={t("providers.available")}
          providers={filteredProviders}
          isLocalhost={isLocalhost}
          mutate={mutate}
        />
      )}
    </>
  );
}
