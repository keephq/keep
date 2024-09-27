"use client"; // Add this line at the top to make this a Client Component

import React, {
  useState,
  useEffect,
  Dispatch,
  SetStateAction,
  useMemo,
} from "react";
import { GenericTable } from "@/components/table/GenericTable";
import { useAlertQualityMetrics } from "utils/hooks/useAlertQuality";
import { useProviders } from "utils/hooks/useProviders";
import {
  Provider,
  Providers,
  ProvidersResponse,
} from "app/providers/providers";
import { TabGroup, TabList, Tab } from "@tremor/react";
import { GenericFilters } from "@/components/filters/GenericFilters";

const tabs = [
  { name: "All", value: "alltime" },
  { name: "Installed", value: "last_30d" },
  { name: "Linked", value: "last_7d" },
];

const ALERT_QUALITY_FILTERS = [
  {
    type: "date",
    key: "time_stamp",
    value: "",
    name: "Last received",
  },
  {
    type: "select",
    key: "field",
    value: "",
    name: "Field",
    options: [
      { value: "team", label: "Team" },
      { value: "application", label: "Application" },
      { value: "subsystem", label: "Subsystem" },
      { value: "severity", label: "Severity" },
      { value: "priority", label: "Priority" },
    ],
  },
];

export const FilterTabs = ({
  tabs,
  setTab,
  tab,
}: {
  tabs: { name: string; value: string }[];
  setTab: Dispatch<SetStateAction<number>>;
  tab: number;
}) => {
  return (
    <div className="max-w-lg space-y-12 pt-6">
      <TabGroup
        index={tab}
        onIndexChange={(index: number) => {
          setTab(index);
        }}
      >
        <TabList variant="solid" color="black" className="bg-gray-300">
          {tabs.map((tabItem, index) => (
            <Tab key={tabItem.value}>{tabItem.name}</Tab>
          ))}
        </TabList>
      </TabGroup>
    </div>
  );
};

interface ProviderAlertQuality {
  alertsReceived: number;
  alertsCorrelatedToIncidentsPercentage: number;
  // alertsWithFieldFilledPercentage: number;
  alertsWithSeverityPercentage: number;
}

interface Pagination {
  limit: number;
  offset: number;
}

const QualityTable = ({
  providersMeta,
  alertsQualityMetrics,
}: {
  providersMeta: ProvidersResponse | undefined;
  alertsQualityMetrics: Record<string, Record<string, any>> | undefined;
}) => {
  const [pagination, setPagination] = useState<Pagination>({
    limit: 10,
    offset: 0,
  });
  const [tab, setTab] = useState(0);

  const handlePaginationChange = (newLimit: number, newOffset: number) => {
    setPagination({ limit: newLimit, offset: newOffset });
  };

  useEffect(() => {
    handlePaginationChange(10, 0);
  },[tab])

  const columns = [
    {
      header: "Provider Name",
      accessorKey: "display_name",
    },
    {
      header: "Alerts Received",
      accessorKey: "alertsReceived",
    },
    {
      header: "% of Alerts Correlated to Incidents",
      accessorKey: "alertsCorrelatedToIncidentsPercentage",
      cell: (info: any) => `${info.getValue().toFixed(2)}%`,
    },
    {
      header: "% of Alerts Having Severity", //we are considering critical and warning as severe
      accessorKey: "alertsWithSeverityPercentage",
      cell: (info: any) => `${info.getValue().toFixed(2)}%`,
    },
  ];

  const finalData = useMemo(() => {
    let providers: Provider[] | null = null;

    if (!providersMeta || !alertsQualityMetrics) {
      return null;
    }

    switch (tab) {
      case 0:
        providers = providersMeta?.providers || providers;
        break;
      case 1:
        providers = providersMeta?.installed_providers || providers;
        break;
      case 2:
        providers = providersMeta.linked_providers || providers;
        break;
      default:
        providers = providersMeta?.providers || providers;
        break;
    }

    if (!providers) {
      return null;
    }

    const innerData: Providers & ProviderAlertQuality[] = [];

    providers.forEach((provider) => {
      const providerType = provider.type;
      const alertQuality = alertsQualityMetrics[providerType];
      const totalAlertsReceived = alertQuality?.total_alerts ?? 0;
      const correlated_alerts = alertQuality?.correlated_alerts ?? 0;
      const correltedPert =
        totalAlertsReceived && correlated_alerts
          ? (correlated_alerts / totalAlertsReceived) * 100
          : 0;
      const severityPert = totalAlertsReceived
        ? ((alertQuality?.severity_count ?? 0) / totalAlertsReceived) * 100
        : 0;
      innerData.push({
        ...provider,
        alertsReceived: totalAlertsReceived,
        alertsCorrelatedToIncidentsPercentage: correltedPert,
        alertsWithSeverityPercentage: severityPert,
      });
    });

    return innerData;
  }, [tab, providersMeta, alertsQualityMetrics]);

  return (
    <>
      <h1 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-4">
        Alert Quality Dashboard
      </h1>
      <div className="flex justify-between  items-end mb-4">
        <FilterTabs tabs={tabs} setTab={setTab} tab={tab} />
        {/* TODO: filters are not working need to intergate with backend logic */}
        <GenericFilters filters={ALERT_QUALITY_FILTERS} />
      </div>
      {finalData && (
        <GenericTable
          data={finalData}
          columns={columns}
          rowCount={finalData?.length}
          offset={pagination.offset}
          limit={pagination.limit}
          onPaginationChange={handlePaginationChange}
          dataFetchedAtOneGO={true}
          onRowClick={(row) => {
            console.log("Row clicked:", row);
          }}
        />
      )}
    </>
  );
};

const AlertQuality = () => {
  const { data: providersMeta } = useProviders();
  const { data: alertsQualityMetrics, error } = useAlertQualityMetrics();

  return (
    <div className="p-4">
      <QualityTable
        providersMeta={providersMeta}
        alertsQualityMetrics={alertsQualityMetrics}
      />
    </div>
  );
};

export default AlertQuality;
