import {useSession} from "next-auth/react";
import {getApiURL} from "@/utils/apiUrl";
import useSWR from "swr";
import {fetcher} from "@/utils/fetcher";

export interface MetricsWidget {
  id: string;
  name: string;
  data: DistributionData[];
}

interface DistributionData {
  hour: string;
  number: number
}

interface DashboardDistributionData {
  mttr: DistributionData[];
  ipd: DistributionData[];
  apd: DistributionData[];
  wpd: DistributionData[];

}

export const useDashboardMetricWidgets = () => {
  const {data: session} = useSession();
  const apiUrl = getApiURL();
  const {data, error, mutate} = useSWR<DashboardDistributionData>(
      session ? `${apiUrl}/dashboard/metric-widgets` : null,
      (url: string) => fetcher(url, session!.accessToken)
  )

  const useGetData = () => {
    return useSWR<DashboardDistributionData>(
        session ? `${apiUrl}/dashboard/metric-widgets` : null,
        (url: string) => fetcher(url, session!.accessToken))
  }
  let widgets: MetricsWidget[] = []
  if (data) {
      widgets = [
      {
        id: "mttr",
        name: "MTTR",
        data: data.mttr
      },
      {
        id: "apd",
        "name": "Alerts/Day",
        data: data.apd
      },
      {
        id: "ipd",
        name: "Incidents/Day",
        data: data.ipd
      },
      {
        id: "wpd",
        name: "Workflows/Day",
        data: data.wpd
      }
    ];
  }
  return {widgets, useGetData};
}