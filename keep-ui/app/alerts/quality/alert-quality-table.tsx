"use client"; // Add this line at the top to make this a Client Component

import React, { useState, useEffect } from 'react';
import { GenericTable } from '@/components/table/GenericTable';
import { useAlertQualityMetrics } from 'utils/hooks/useAlertQuality';
import { useProviders } from 'utils/hooks/useProviders';
import { Providers } from 'app/providers/providers';

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
const AlertQualityTable = () => {
  const {data: providersMeta} = useProviders(); 
  const {data: alertsQualityMetrics, error} =  useAlertQualityMetrics()
  const [pagination, setPagination] = useState<Pagination>({
    limit: 25,
    offset: 0,
});
  const columns = [
    {
      header: 'Provider Name',
      accessorKey: 'display_name',
    },
    {
      header: 'Alerts Received',
      accessorKey: 'alertsReceived',
    },
    {
      header: '% of Alerts Correlated to Incidents',
      accessorKey: 'alertsCorrelatedToIncidentsPercentage',
      cell: (info: any) => `${info.getValue().toFixed(2)}%`,
    },
    {
      header: '% of Alerts Having Severity',//we are considering critical and warning as severe
      accessorKey: 'alertsWithSeverityPercentage',
      cell: (info: any) => `${info.getValue().toFixed(2)}%`,
    },
  ];

  const finalData: Providers&ProviderAlertQuality[] = [];
  const providers =  providersMeta?.providers;


  if (alertsQualityMetrics && providers) {
    providers.forEach( provider => {
      const  providerType = provider.type;
      const alertQuality = alertsQualityMetrics[providerType];
      const totalAlertsReceived = alertQuality?.total_alerts ?? 0;
      const correlated_alerts = alertQuality?.correlated_alerts ?? 0;
      const correltedPert = totalAlertsReceived && correlated_alerts ? (correlated_alerts/totalAlertsReceived)*100 : 0;
      const severityPert = totalAlertsReceived ? ((alertQuality?.severity_count ?? 0)/totalAlertsReceived)*100 : 0
      finalData.push({
        ...provider,
        alertsReceived: totalAlertsReceived,
        alertsCorrelatedToIncidentsPercentage: correltedPert,
        alertsWithSeverityPercentage: severityPert,
      });
    });
  }

  const handlePaginationChange = (newLimit: number, newOffset: number) => {
    setPagination({ limit: newLimit, offset: newOffset })
  };


  return (
    <div className="p-4">
        <h1 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-4">
            Alert Quality Dashboard
        </h1>
        {providers && alertsQualityMetrics && <GenericTable
            data={finalData}
            columns={columns}
            rowCount={finalData?.length}
            offset={pagination.offset}
            limit={pagination.limit}
            onPaginationChange={handlePaginationChange}
            dataFetchedAtOneGO={true}
            onRowClick={(row) => {
                console.log('Row clicked:', row);
            }}
        />}
    </div>
  );
};

export default AlertQualityTable;
