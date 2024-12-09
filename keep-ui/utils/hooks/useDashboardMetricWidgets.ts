import useSWR from "swr";
import { useSearchParams } from "next/navigation";
import { useApi } from "@/shared/lib/hooks/useApi";

export interface MetricsWidget {
  id: string;
  name: string;
  data: DistributionData[];
}

interface DistributionData {
  hour: string;
  number: number;
}

interface DashboardDistributionData {
  mttr: DistributionData[];
  ipd: DistributionData[];
  apd: DistributionData[];
  wpd: DistributionData[];
}

export const useDashboardMetricWidgets = (useFilters?: boolean) => {
  const api = useApi();
  const searchParams = useSearchParams();
  const filters = searchParams?.toString();

  const { data, error, mutate } = useSWR<DashboardDistributionData>(
    api.isReady()
      ? `/dashboard/metric-widgets${useFilters && filters ? `?${filters}` : ""}`
      : null,
    (url: string) => api.get(url)
  );

  let widgets: MetricsWidget[] = [];
  if (data) {
    widgets = [
      {
        id: "mttr",
        name: "MTTR",
        data: data.mttr,
      },
      {
        id: "apd",
        name: "Alerts/Day",
        data: data.apd,
      },
      {
        id: "ipd",
        name: "Incidents/Day",
        data: data.ipd,
      },
      {
        id: "wpd",
        name: "Workflows/Day",
        data: data.wpd,
      },
    ];
  }
  return { widgets };
};
