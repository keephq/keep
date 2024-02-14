import { Dialog, Transition } from "@headlessui/react";
import { Fragment, useState } from "react";
import { AlertDto } from "./models";
import { AlertTable } from "./alert-table";
import { useAlertTableCols } from "./alert-table-utils";
import { Button, Flex, Subtitle, Title, Divider } from "@tremor/react";
import AlertHistoryCharts from "./alert-history-charts";
import { useAlerts } from "utils/hooks/useAlerts";
import { PaginationState } from "@tanstack/react-table";
import { useRouter, useSearchParams } from "next/navigation";
import { toDateObjectWithFallback } from "utils/helpers";
import Image from "next/image";
import Modal from "@/components/ui/Modal";

interface AlertHistoryPanelProps {
  alertsHistoryWithDate: (Omit<AlertDto, "lastReceived"> & {
    lastReceived: Date;
  })[];
}

const AlertHistoryPanel = ({
  alertsHistoryWithDate,
}: AlertHistoryPanelProps) => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const currentPreset = searchParams
    ? searchParams.get("selectedPreset")
    : "Feed";

  const [rowPagination, setRowPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  });
  const alertTableColumns = useAlertTableCols();

  const sortedHistoryAlert = alertsHistoryWithDate.map((alert) =>
    alert.lastReceived.getTime()
  );

  const maxLastReceived = new Date(Math.max(...sortedHistoryAlert));
  const minLastReceived = new Date(Math.min(...sortedHistoryAlert));

  if (alertsHistoryWithDate.length === 0) {
    return (
      <div className="flex justify-center">
        <Image
          src="/keep_loading_new.gif"
          alt="loading"
          width={200}
          height={200}
        />
      </div>
    );
  }

  return (
    <Fragment>
      <Flex alignItems="center" justifyContent="between">
        <div>
          <Title>History of: {alertsHistoryWithDate.at(0)?.name}</Title>
          <Subtitle>Total alerts: {alertsHistoryWithDate.length}</Subtitle>
          <Subtitle>First Occurence: {minLastReceived.toString()}</Subtitle>
          <Subtitle>Last Occurence: {maxLastReceived.toString()}</Subtitle>
        </div>
        <Button
          className="mt-2 bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:border-gray-300"
          onClick={() =>
            router.replace(`/alerts?selectedPreset=${currentPreset}`, {
              scroll: false,
            })
          }
        >
          Close
        </Button>
      </Flex>
      <Divider />
      {alertsHistoryWithDate.length && (
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
        isMenuColDisplayed={false}
        isRefreshAllowed={false}
        rowPagination={{
          state: rowPagination,
          onChange: setRowPagination,
        }}
        presetName="alert-history"
      />
    </Fragment>
  );
};

interface Props {
  alerts: AlertDto[];
}

export function AlertHistory({ alerts }: Props) {
  const router = useRouter();

  const searchParams = useSearchParams();
  const selectedAlert = alerts.find((alert) =>
    searchParams
      ? searchParams.get("fingerprint") === alert.fingerprint
      : undefined
  );
  const currentPreset = searchParams
    ? searchParams.get("selectedPreset")
    : "Feed";

  const { useAlertHistory } = useAlerts();
  const { data: alertHistory = [] } = useAlertHistory(selectedAlert, {
    revalidateOnFocus: false,
  });

  const alertsHistoryWithDate = alertHistory.map((alert) => ({
    ...alert,
    lastReceived: toDateObjectWithFallback(alert.lastReceived),
  }));

  return (
    <Modal
      isOpen={selectedAlert !== undefined}
      onClose={() =>
        router.replace(`/alerts?selectedPreset=${currentPreset}`, {
          scroll: false,
        })
      }
      className="w-full max-w-screen-2xl max-h-[710px] transform overflow-scroll ring-tremor bg-white
                    p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
    >
      <AlertHistoryPanel alertsHistoryWithDate={alertsHistoryWithDate} />
    </Modal>
  );
}
