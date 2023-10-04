"use client";
import { FrigadeAnnouncement } from "@frigade/react";
import { Providers, defaultProvider, Provider } from "./providers";
import { useSession } from "../../utils/customAuth";
import { getApiURL } from "../../utils/apiUrl";
import { fetcher } from "../../utils/fetcher";
import { KeepApiError } from "../error";
import ProvidersAvailable from "./providers-available";
import React, { useState, Suspense, useContext, useEffect } from "react";
import useSWR from "swr";
import Loading from "../loading";
import Image from "next/image";
import ProvidersInstalled from "./providers-installed";
import { LayoutContext } from "./context";
import { toast } from "react-toastify";
import { updateIntercom } from "@/components/ui/Intercom";

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
        oauth2_url: provider.oauth2_url,
        scopes: provider.scopes,
        validatedScopes: provider.validatedScopes,
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
  } = useFetchProviders();
  const { searchProviderString } = useContext(LayoutContext);

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

  const searchProviders = (provider: Provider) => {
    return (
      !searchProviderString ||
      provider.type?.toLowerCase().includes(searchProviderString)
    );
  };

  return (
    <Suspense
      fallback={
        <Image src="/keep.gif" width={200} height={200} alt="Loading" />
      }
    >
      <FrigadeAnnouncement
        flowId="flow_VpefBUPWpliWceBm"
        modalPosition="center"
        onButtonClick={(stepData, index, cta) => {
          if (cta === "primary") {
            window.open(
              "https://calendly.com/d/4p7-8dg-399/keep-onboarding",
              "_blank"
            );
          }
          return true;
        }}
      />
      <ProvidersInstalled
        providers={installedProviders}
        onDelete={deleteProvider}
      />
      <ProvidersAvailable
        providers={providers.filter(searchProviders)}
        addProvider={addProvider}
      />
    </Suspense>
  );
}
