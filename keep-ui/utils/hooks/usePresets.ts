import { Preset } from "app/alerts/models";
import { useSession } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const usePresets = () => {
  const apiUrl = getApiURL();
  const { data: session } = useSession();
  const searchParams = useSearchParams()!;

  const getCurrentPreset = () => {
    return searchParams?.get("selectedPreset") || "Feed";
  };

  const useAllPresets = (options?: SWRConfiguration) => {
    return useSWR<Preset[]>(
      () => (session ? `${apiUrl}/preset` : null),
      async (url) => fetcher(url, session?.accessToken),
      options
    );
  };

  return { useAllPresets, getCurrentPreset };
};
