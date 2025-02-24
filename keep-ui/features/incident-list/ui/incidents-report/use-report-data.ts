import { useApi } from "@/shared/lib/hooks/useApi";
import { IncidentData } from "./models";
import { useEffect, useState } from "react";

export const useReportData = (filterCel: string) => {
  const api = useApi();
  const [data, setData] = useState<IncidentData | null>();

  let requestUrl = `/incidents/report`;

  if (filterCel) {
    requestUrl += `?cel=${filterCel}`;
  }

  useEffect(() => {
    if (api.isReady()) {
      setData(null);
      api.get(requestUrl).then((data) => setData(data));
    }
  }, [api, api.isReady(), requestUrl]);

  return {
    data,
    isLoading: !data,
  };
};
