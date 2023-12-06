import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  Icon,
  Callout,
  Text,
  Button,
  Select,
  SelectItem,
} from "@tremor/react";
import { AlertsTableBody } from "./alerts-table-body";
import { Alert, AlertTableKeys } from "./models";
import { useEffect, useState } from "react";
import { AlertTransition } from "./alert-transition";
import {
  CircleStackIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";
import { Provider } from "app/providers/providers";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  TableCellsIcon,
} from "@heroicons/react/20/solid";
import { User } from "app/settings/models";
import { User as NextUser } from "next-auth";

interface Props {
  alerts: Alert[];
  groupBy?: string;
  groupedByAlerts?: { [key: string]: Alert[] };
  workflows?: any[];
  providers?: Provider[];
  mutate?: () => void;
  isAsyncLoading?: boolean;
  onDelete?: (
    fingerprint: string,
    lastReceived: Date,
    restore?: boolean
  ) => void;
  setAssignee?: (fingerprint: string, unassign: boolean) => void;
  users?: User[];
  currentUser: NextUser;
  deletedCount?: number;
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
  setAssignee,
  users = [],
  currentUser,
  deletedCount = 0,
}: Props) {
  const [selectedAlertHistory, setSelectedAlertHistory] = useState<Alert[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [defaultPageSize, setDefaultPageSize] = useState(10);

  const closeModal = (): any => setIsOpen(false);
  const openModal = (alert: Alert): any => {
    setSelectedAlertHistory(groupedByAlerts[(alert as any)[groupBy!]]);
    setIsOpen(true);
  };

  useEffect(() => {
    setCurrentPage(1);
  }, [alerts]);

  function renderPagination() {
    if (!defaultPageSize) return null;

    const totalPages = Math.ceil(alerts.length / defaultPageSize);
    const startItem = (currentPage - 1) * defaultPageSize + 1;
    const endItem = Math.min(currentPage * defaultPageSize, alerts.length);

    return (
      <div className="flex justify-between items-center">
        <Text>
          Showing {alerts.length === 0 ? 0 : startItem} – {endItem} of{" "}
          {alerts.length}{" "}
          {deletedCount > 0 && `(there are ${deletedCount} deleted alerts)`}
        </Text>
        <div className="flex">
          <Select
            value={defaultPageSize.toString()}
            enableClear={false}
            onValueChange={(value) => {
              setDefaultPageSize(parseInt(value));
              setCurrentPage(1);
            }}
            className="mr-2"
            icon={TableCellsIcon}
          >
            <SelectItem value="10">10</SelectItem>
            <SelectItem value="20">20</SelectItem>
            <SelectItem value="50">50</SelectItem>
            <SelectItem value="100">100</SelectItem>
          </Select>
          <Button
            icon={ArrowLeftIcon}
            onClick={() => setCurrentPage(currentPage - 1)}
            size="xs"
            color="orange"
            variant="secondary"
            disabled={currentPage === 1}
          />
          <Button
            icon={ArrowRightIcon}
            onClick={() => setCurrentPage(currentPage + 1)}
            size="xs"
            disabled={currentPage === totalPages}
            color="orange"
            variant="secondary"
          />
        </div>
      </div>
    );
  }

  const startIndex = (currentPage - 1) * defaultPageSize;
  const endIndex = startIndex + defaultPageSize;

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
          alerts={alerts
            .sort((a, b) => b.lastReceived.getTime() - a.lastReceived.getTime())
            .slice(startIndex, endIndex)}
          groupBy={groupBy}
          groupedByData={groupedByAlerts}
          openModal={openModal}
          workflows={workflows}
          providers={providers}
          mutate={mutate}
          showSkeleton={isAsyncLoading}
          onDelete={onDelete}
          setAssignee={setAssignee}
          users={users}
          currentUser={currentUser}
        />
      </Table>
      {renderPagination()}
      <AlertTransition
        isOpen={isOpen}
        closeModal={closeModal}
        data={selectedAlertHistory}
        users={users}
        currentUser={currentUser}
      />
    </>
  );
}
