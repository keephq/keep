import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  Icon,
  Callout,
} from "@tremor/react";
import { AlertsTableBody } from "./alerts-table-body";
import { Alert, AlertTableKeys } from "./models";
import { useState } from "react";
import { AlertTransition } from "./alert-transition";
import {
  CircleStackIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { Provider } from "app/providers/providers";

interface Props {
  data: Alert[];
  groupBy?: string;
  workflows?: any[];
  providers?: Provider[];
  mutate?: () => void;
  isAsyncLoading?: boolean;
  onDelete?: (fingerprint: string, restore?: boolean) => void;
  showDeleted?: boolean;
}

export function AlertTable({
  data: alerts,
  groupBy,
  workflows,
  providers,
  mutate,
  isAsyncLoading = false,
  onDelete,
  showDeleted = false,
}: Props) {
  const [selectedAlertHistory, setSelectedAlertHistory] = useState<Alert[]>([]);
  const [isOpen, setIsOpen] = useState(false);

  function showDeletedAlert(alert: Alert): boolean {
    return showDeleted || !alert.deleted;
  }

  let groupedByAlerts = {} as { [key: string]: Alert[] };
  const deletedAlertFingerprints = new Set(
    alerts.filter((alert) => alert.deleted).map((alert) => alert.fingerprint)
  );
  let aggregatedAlerts = alerts.map((alert) => {
    alert.lastReceived = new Date(alert.lastReceived);
    if (deletedAlertFingerprints.has(alert.fingerprint)) {
      alert.deleted = true;
    }
    return alert;
  });

  if (groupBy) {
    // Group alerts by the groupBy key
    groupedByAlerts = alerts.reduce((acc, alert) => {
      const key = (alert as any)[groupBy] as string;
      if (!acc[key]) {
        acc[key] = [alert];
      } else {
        acc[key].push(alert);
      }
      return acc;
    }, groupedByAlerts);
    // Sort by last received
    Object.keys(groupedByAlerts).forEach((key) =>
      groupedByAlerts[key].sort(
        (a, b) => b.lastReceived.getTime() - a.lastReceived.getTime()
      )
    );
    // Only the last state of each alert is shown if we group by something
    aggregatedAlerts = Object.keys(groupedByAlerts).map(
      (key) => groupedByAlerts[key][0]
    );
  }

  const closeModal = (): any => setIsOpen(false);
  const openModal = (alert: Alert): any => {
    setSelectedAlertHistory(groupedByAlerts[(alert as any)[groupBy!]]);
    setIsOpen(true);
  };

  return (
    <>
      {isAsyncLoading && (
        <Callout
          title="Getting your alerts..."
          icon={CircleStackIcon}
          color="gray"
          className="mt-5"
        >
          Alerts will show up in this table as they are added to Keep...
        </Callout>
      )}
      <Table>
        <TableHead>
          <TableRow>
            {<TableHeaderCell>{/** Menu */}</TableHeaderCell>}
            {Object.keys(AlertTableKeys).map((key) => (
              <TableHeaderCell key={key}>
                <div className="flex items-center">
                  {key}{" "}
                  {AlertTableKeys[key] !== "" && (
                    <Icon
                      icon={QuestionMarkCircleIcon}
                      tooltip={AlertTableKeys[key]}
                      variant="simple"
                      color="gray"
                    />
                  )}{" "}
                </div>
              </TableHeaderCell>
            ))}
          </TableRow>
        </TableHead>
        <AlertsTableBody
          data={aggregatedAlerts.filter(showDeletedAlert)}
          groupBy={groupBy}
          groupedByData={groupedByAlerts}
          openModal={openModal}
          workflows={workflows}
          providers={providers}
          mutate={mutate}
          showSkeleton={isAsyncLoading}
          onDelete={onDelete}
        />
      </Table>
      <AlertTransition
        isOpen={isOpen}
        closeModal={closeModal}
        data={selectedAlertHistory}
      />
    </>
  );
}
