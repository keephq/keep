import { useApi } from "@/shared/lib/hooks/useApi";
import useSWR from "swr";
import { IncidentData } from "./models";

export const useReportData = (incidentIds: string[]) => {
  const api = useApi();
  const ids_query = incidentIds.map((id) => `'${id}'`).join(",");
  const cel_query = `id in [${ids_query}]`;
  const requestUrl = `/incidents/report?cel=${cel_query}`;

  const swrValue = useSWR<IncidentData>(
    () => (api.isReady() ? requestUrl : null),
    (url) => api.get(url),
    { revalidateOnFocus: false }
  );
  return swrValue;
};
