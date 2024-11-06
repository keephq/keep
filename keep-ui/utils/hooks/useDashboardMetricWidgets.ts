import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useApiUrl } from "./useConfig";
import useSWR from "swr";
import { fetcher } from "@/utils/fetcher";
import { usePathname, useSearchParams } from "next/navigation";

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
  const { data: session } = useSession();
  const apiUrl = useApiUrl();
  const searchParams = useSearchParams();
  const filters = searchParams?.toString();

  const { data, error, mutate } = useSWR<DashboardDistributionData>(
    session
      ? `${apiUrl}/dashboard/metric-widgets${
          useFilters && filters ? `?${filters}` : ""
        }`
      : null,
    (url: string) => fetcher(url, session!.accessToken)
  );
  console.log(filters);

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
