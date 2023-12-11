import { ArrowPathIcon, TableCellsIcon } from "@heroicons/react/24/outline";
import { ArrowLeftIcon, ArrowRightIcon } from "@radix-ui/react-icons";
import { Button, Select, SelectItem, Text } from "@tremor/react";
import { Dispatch, SetStateAction, useEffect, useState } from "react";
import { AlertDto } from "./models";

interface Props {
  alerts: AlertDto[];
  mutate?: () => void;
  deletedCount: number;
  setStartIndex: Dispatch<SetStateAction<number>>;
  setEndIndex: Dispatch<SetStateAction<number>>;
}

export default function AlertPagination({
  alerts,
  deletedCount,
  mutate,
  setStartIndex,
  setEndIndex,
}: Props) {
  const [currentPage, setCurrentPage] = useState(1);
  const [defaultPageSize, setDefaultPageSize] = useState(10);
  const [reloadLoading, setReloadLoading] = useState<boolean>(false);
  const totalPages = Math.ceil(alerts.length / defaultPageSize);
  const startItem = (currentPage - 1) * defaultPageSize + 1;
  const endItem = Math.min(currentPage * defaultPageSize, alerts.length);
  const startIndex = (currentPage - 1) * defaultPageSize;

  useEffect(() => {
    setCurrentPage(1);
  }, [alerts]);

  useEffect(() => {
    setStartIndex(startIndex);
    setEndIndex(startIndex + defaultPageSize);
  }, [startIndex, defaultPageSize, setStartIndex, setEndIndex]);

  if (!defaultPageSize) return null;

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
          className="mr-1"
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
        {mutate !== undefined && (
          <Button
            icon={ArrowPathIcon}
            color="orange"
            size="xs"
            className="ml-2.5"
            disabled={reloadLoading}
            loading={reloadLoading}
            onClick={async () => {
              setReloadLoading(true);
              await mutate!();
              setReloadLoading(false);
            }}
            title="Refresh"
          ></Button>
        )}
      </div>
    </div>
  );
}
