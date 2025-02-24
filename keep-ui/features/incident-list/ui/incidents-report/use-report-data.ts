import { useApi } from "@/shared/lib/hooks/useApi";
import useSWR from "swr";
import { IncidentData } from "./models";

export const useReportData = (filterCel: string) => {
  const api = useApi();
  let requestUrl = `/incidents/report`;

  if (filterCel) {
    requestUrl += `?cel=${filterCel}`;
  }

  const swrValue = useSWR<IncidentData>(
    () => (api.isReady() ? requestUrl : null),
    (url) => api.get(url),
    { revalidateOnFocus: false }
  );
  return swrValue;
};
