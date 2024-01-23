import { Dialog, Transition } from "@headlessui/react";
import { Fragment, useMemo, useState } from "react";
import { AlertDto } from "./models";
import { AlertTable, getAlertTableColumns } from "./alert-table";
import { Button, Flex, Subtitle, Title, Divider } from "@tremor/react";
import AlertHistoryCharts from "./alert-history-charts";
import { useAlerts } from "utils/hooks/useAlerts";
import Loading from "app/loading";
import { PaginationState } from "@tanstack/react-table";
import { useRouter, useSearchParams } from "next/navigation";

interface Props {
  alerts: AlertDto[];
}

export function AlertHistory({ alerts }: Props) {
  const [rowPagination, setRowPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  });

  const router = useRouter();

  const searchParams = useSearchParams();
  const selectedAlert = alerts.find((alert) =>
    searchParams ? searchParams.get("id") === alert.id : undefined
  );

  const { useAlertHistory } = useAlerts();
  const { data: alertHistory = [], isLoading } = useAlertHistory(
    selectedAlert,
    {
      revalidateOnFocus: false,
    }
  );

  const alertTableColumns = useMemo(() => getAlertTableColumns(), []);

  if (isLoading) {
    return <Loading />;
  }

  const alertsHistoryWithDate = alertHistory.map((alert) => ({
    ...alert,
    lastReceived: new Date(alert.lastReceived),
  }));

  const sortedHistoryAlert = alertsHistoryWithDate
    .sort((a, b) => a.lastReceived.getTime() - b.lastReceived.getTime())
    .map((alert) => alert.lastReceived.getTime());

  const maxLastReceived = new Date(Math.max(...sortedHistoryAlert));
  const minLastReceived = new Date(Math.min(...sortedHistoryAlert));

  return (
    <Transition appear show={selectedAlert !== undefined} as={Fragment}>
      <Dialog
        as="div"
        className="relative z-50"
        onClose={() => router.replace("/alerts", { scroll: false })}
      >
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-900 bg-opacity-25" />
        </Transition.Child>
        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel
                className="w-full max-w-screen-2xl max-h-[710px] transform overflow-scroll ring-tremor bg-white
                                    p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
              >
                <Flex alignItems="center" justifyContent="between">
                  <div>
                    <Title>History of: {alertsHistoryWithDate[0]?.name}</Title>
                    <Subtitle>
                      Total alerts: {alertsHistoryWithDate.length}
                    </Subtitle>
                    <Subtitle>
                      First Occurence: {minLastReceived.toString()}
                    </Subtitle>
                    <Subtitle>
                      Last Occurence: {maxLastReceived.toString()}
                    </Subtitle>
                  </div>
                  <Button
                    className="mt-2 bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:border-gray-300"
                    onClick={() => router.replace("/alerts", { scroll: false })}
                  >
                    Close
                  </Button>
                </Flex>
                <Divider />
                {selectedAlert && (
                  <AlertHistoryCharts
                    maxLastReceived={maxLastReceived}
                    minLastReceived={minLastReceived}
                    alerts={alertsHistoryWithDate}
                  />
                )}
                <Divider />
                <AlertTable
                  alerts={alertsHistoryWithDate}
                  columns={alertTableColumns}
                  columnsToExclude={["description"]}
                  isMenuColDisplayed={false}
                  isRefreshAllowed={false}
                  rowPagination={{
                    state: rowPagination,
                    onChange: setRowPagination,
                  }}
                />
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
