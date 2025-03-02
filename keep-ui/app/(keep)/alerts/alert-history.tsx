import { Fragment, useState } from "react";
import { AlertDto, AlertKnownKeys } from "@/entities/alerts/model";
import { AlertTable } from "./alert-table";
import { useAlertTableCols } from "./alert-table-utils";
import { Button, Flex, Subtitle, Title, Divider } from "@tremor/react";
import AlertHistoryCharts from "./alert-history-charts";
import { useAlerts } from "utils/hooks/useAlerts";
import { useRouter, useSearchParams } from "next/navigation";
import { toDateObjectWithFallback } from "utils/helpers";
import Image from "next/image";
import Modal from "@/components/ui/Modal";
import AlertNoteModal from "@/app/(keep)/alerts/alert-note-modal";

interface AlertHistoryPanelProps {
  alertsHistoryWithDate: (Omit<AlertDto, "lastReceived"> & {
    lastReceived: Date;
  })[];
  presetName: string;
}

const AlertHistoryPanel = ({
  alertsHistoryWithDate,
  presetName,
}: AlertHistoryPanelProps) => {
  const router = useRouter();
  const [noteModalAlert, setNoteModalAlert] = useState<AlertDto | null>(null);

  const additionalColsToGenerate = [
    ...new Set(
      alertsHistoryWithDate.flatMap((alert) => {
        const keys = Object.keys(alert).filter(
          (key) => !AlertKnownKeys.includes(key)
        );
        return keys.flatMap((key) => {
          if (
            typeof alert[key as keyof AlertDto] === "object" &&
            alert[key as keyof AlertDto] !== null
          ) {
            return Object.keys(alert[key as keyof AlertDto] as object).map(
              (subKey) => `${key}.${subKey}`
            );
          }
          return key;
        });
      })
    ),
  ];

  const alertTableColumns = useAlertTableCols({
    additionalColsToGenerate: additionalColsToGenerate,
    setNoteModalAlert: setNoteModalAlert,
    noteReadOnly: true,
    presetName: alertsHistoryWithDate.at(0)?.fingerprint ?? "",
  });

  const sortedHistoryAlert = alertsHistoryWithDate.map((alert) =>
    alert.lastReceived.getTime()
  );

  const maxLastReceived = new Date(Math.max(...sortedHistoryAlert));
  const minLastReceived = new Date(Math.min(...sortedHistoryAlert));

  if (alertsHistoryWithDate.length === 0) {
    return (
      <div className="flex justify-center">
        <Image
          className="animate-bounce"
          src="/keep.svg"
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
        <div className="w-11/12">
          <Title className="truncate">
            History of: {alertsHistoryWithDate.at(0)?.name}
          </Title>
          <Subtitle>
            Showing: {alertsHistoryWithDate.length} alerts (1000 maximum)
          </Subtitle>
          <Subtitle>First Occurence: {minLastReceived.toString()}</Subtitle>
          <Subtitle>Last Occurence: {maxLastReceived.toString()}</Subtitle>
        </div>
        <Button
          className="mt-2 bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:border-gray-300"
          onClick={() => router.replace(`/alerts/${presetName.toLowerCase()}`)}
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
        presetName="alert-history"
      />
      <AlertNoteModal
        handleClose={() => setNoteModalAlert(null)}
        alert={noteModalAlert ?? null}
        readOnly={true}
      />
    </Fragment>
  );
};

interface Props {
  alerts: AlertDto[];
  presetName: string;
}

export function AlertHistory({ alerts, presetName }: Props) {
  const router = useRouter();

  const searchParams = useSearchParams();
  const selectedAlert = alerts.find((alert) =>
    searchParams
      ? searchParams.get("fingerprint") === alert.fingerprint
      : undefined
  );

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
      onClose={() => {
        router.replace(`/alerts/${presetName.toLowerCase()}`);
      }}
      className="w-full max-w-screen-2xl max-h-[710px] transform overflow-scroll ring-tremor bg-white
                    p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
    >
      <AlertHistoryPanel
        alertsHistoryWithDate={alertsHistoryWithDate}
        presetName={presetName}
      />
    </Modal>
  );
}
