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
  alerts: Alert[];
  groupBy?: string;
  groupedByAlerts?: { [key: string]: Alert[] };
  workflows?: any[];
  providers?: Provider[];
  mutate?: () => void;
  isAsyncLoading?: boolean;
  onDelete?: (fingerprint: string, restore?: boolean) => void;
}

export function AlertTable({
  alerts,
  groupedByAlerts = {},
  groupBy,
  workflows,
  providers,
  mutate,
  isAsyncLoading = false,
  onDelete,
}: Props) {
  const [selectedAlertHistory, setSelectedAlertHistory] = useState<Alert[]>([]);
  const [isOpen, setIsOpen] = useState(false);

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
          alerts={alerts}
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
