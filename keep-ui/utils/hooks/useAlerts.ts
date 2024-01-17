import { AlertDto } from "app/alerts/models";
import { useSession } from "next-auth/react";
import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";

export const useAlerts = () => {
  const { data: session } = useSession();
  const apiUrl = getApiURL();

  const useAlertHistory = (
    selectedAlert?: AlertDto,
    options?: SWRConfiguration
  ) => {
    const url = selectedAlert
      ? `${apiUrl}/alerts/${selectedAlert.fingerprint}/history/?provider_id=${
          selectedAlert.providerId
        }&provider_type=${selectedAlert.source ? selectedAlert.source[0] : ""}`
      : null;

    return useSWR<AlertDto[]>(
      url,
      (url) => fetcher(url, session?.accessToken),
      options
    );
  };

  return { useAlertHistory };
};
