"use client"; // Add this line at the top to make this a Client Component

import React, { useState, useEffect } from 'react';
import { useFetchProviders } from 'app/providers/page.client';
import { GenericTable } from '@/components/table/GenericTable';

interface ProviderAlertQuality {
  providerName: string;
  alertsReceived: number;
  alertsCorrelatedToIncidentsPercentage: number;
  alertsWithFieldFilledPercentage: number;
}

const AlertQualityTable = () => {
  const {installedProviders} = useFetchProviders();
  const [data, setData] = useState<ProviderAlertQuality[]>([]);
  const [rowCount, setRowCount] = useState<number>(0);
  const [offset, setOffset] = useState<number>(0);
  const [limit, setLimit] = useState<number>(10);

  const columns = [
    {
      header: 'Provider Name',
      accessorKey: 'providerName',
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
      header: '% of Alerts Having Field Filled',
      accessorKey: 'alertsWithFieldFilledPercentage',
      cell: (info: any) => `${info.getValue().toFixed(2)}%`,
    },
  ];

  useEffect(() => {
    const fetchData = async () => {
      try {
        const transformedData = installedProviders.map((provider: any) => ({
          providerName: `${provider.details.name}  (${provider.display_name})` || 'Unknown',
          alertsReceived: provider.alertsReceived || 0,
          alertsCorrelatedToIncidentsPercentage: provider.alertsCorrelatedToIncidentsPercentage * 100 || 0,
          alertsWithFieldFilledPercentage: provider.alertsWithFieldFilledPercentage * 100 || 0,
        }));

        setData(transformedData);
        setRowCount(transformedData.length);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      }
    };

    fetchData();
  }, [offset, limit]);

  const handlePaginationChange = (newLimit: number, newOffset: number) => {
    setLimit(newLimit);
    setOffset(newOffset);
  };

  return (
    <div className="p-4">
        <h1 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-4">
            Alert Quality Dashboard
        </h1>
        <GenericTable
            data={data}
            columns={columns}
            rowCount={rowCount}
            offset={offset}
            limit={limit}
            onPaginationChange={handlePaginationChange}
            onRowClick={(row) => {
                console.log('Row clicked:', row);
            }}
        />
    </div>
  );
};

export default AlertQualityTable;
