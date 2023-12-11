import { Dialog, Transition } from "@headlessui/react";
import { Fragment, useEffect, useState } from "react";
import { AlertDto } from "./models";
import { AlertTable } from "./alert-table";
import {
  Button,
  Flex,
  LineChart,
  Subtitle,
  Title,
  Divider,
} from "@tremor/react";
import { User } from "app/settings/models";
import { User as NextUser } from "next-auth";
import Loading from "app/loading";
import AlertPagination from "./alert-pagination";

interface Props {
  isOpen: boolean;
  closeModal: () => void;
  data: AlertDto[];
  users?: User[];
  currentUser: NextUser;
}

export function AlertHistory({
  isOpen,
  closeModal,
  data,
  users = [],
  currentUser,
}: Props) {
  if (!data) {
    return <></>;
  }

  const lastReceivedData = data.map((alert) => alert.lastReceived);
  const maxLastReceived: Date = new Date(
    Math.max(...lastReceivedData.map((date) => date.getTime()))
  );
  const minLastReceived: Date = new Date(
    Math.min(...lastReceivedData.map((date) => date.getTime()))
  );
  const timeDifference: number =
    maxLastReceived.getTime() - minLastReceived.getTime();
  let timeUnit = "Days";
  if (timeDifference < 3600000) {
    // Less than 1 hour (in milliseconds)
    timeUnit = "Minutes";
  } else if (timeDifference < 86400000) {
    // Less than 24 hours (in milliseconds)
    timeUnit = "Hours";
  }

  const [chartData, setChartData] = useState<any[] | null>(null);
  const [categoriesByStatus, setCategoriesByStatus] = useState<string[]>([]);
  const [startIndex, setStartIndex] = useState<number>(0);
  const [endIndex, setEndIndex] = useState<number>(0);

  useEffect(() => {
    const categoriesByStatus: string[] = [];
    const rawChartData = data
      .sort((a, b) => a.lastReceived.getTime() - b.lastReceived.getTime())
      .reduce((prev, curr) => {
        const date = curr.lastReceived;
        let dateKey: string;
        if (timeUnit === "Minutes") {
          dateKey = `${date.getHours()}:${date.getMinutes()}:${date.getSeconds()}`;
        } else if (timeUnit === "Hours") {
          dateKey = `${date.getHours()}:${date.getMinutes()}`;
        } else {
          dateKey = `${date.getDate()}/${
            date.getMonth() + 1
          }/${date.getFullYear()}`;
        }
        if (!prev[dateKey]) {
          prev[dateKey] = {
            [curr.status]: 1,
          };
        } else {
          prev[dateKey][curr.status]
            ? (prev[dateKey][curr.status] += 1)
            : (prev[dateKey][curr.status] = 1);
        }
        if (categoriesByStatus.includes(curr.status) === false) {
          categoriesByStatus.push(curr.status);
        }
        return prev;
      }, {} as { [date: string]: any });

    setCategoriesByStatus(categoriesByStatus);
    setChartData(
      Object.keys(rawChartData).map((key) => {
        return { ...rawChartData[key], date: key };
      })
    );
  }, [data, timeUnit]);

  const currentStateAlerts = data
    .sort((a, b) => b.lastReceived.getTime() - a.lastReceived.getTime())
    .slice(startIndex, endIndex);
  const deletedCount = data.filter((alert) =>
    alert.deleted.includes(alert.lastReceived.toISOString())
  ).length;

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={closeModal}>
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
                    <Title>History of: &quot;{data[0]?.name}&quot;</Title>
                    <Subtitle>Total alerts: {data.length}</Subtitle>
                    <Subtitle>
                      First alert: {minLastReceived.toString()}
                    </Subtitle>
                    <Subtitle>
                      Last alert: {maxLastReceived.toString()}
                    </Subtitle>
                  </div>
                  <Button
                    className="mt-2 bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:border-gray-300"
                    onClick={closeModal}
                  >
                    Close
                  </Button>
                </Flex>
                <Divider />
                {chartData === null ? (
                  <Loading />
                ) : (
                  <LineChart
                    className="mt-6 max-h-56"
                    data={chartData!}
                    index="date"
                    categories={categoriesByStatus}
                    yAxisWidth={40}
                  />
                )}
                <Divider />
                <AlertTable
                  alerts={currentStateAlerts}
                  users={users}
                  currentUser={currentUser}
                />
                <AlertPagination
                  alerts={data}
                  setEndIndex={setEndIndex}
                  setStartIndex={setStartIndex}
                  deletedCount={deletedCount}
                />
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
