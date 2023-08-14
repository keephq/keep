import { Dialog, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { Alert } from "./models";
import { AlertTable } from "./alert-table";
import { Button, Flex, Title } from "@tremor/react";

interface Props {
  isOpen: boolean;
  closeModal: () => void;
  data: Alert[];
}

export function AlertTransition({ isOpen, closeModal, data }: Props) {
  // const rawChartData = data.reduce((prev, curr) => {
  //   const date = Intl.DateTimeFormat("en-US").format(
  //     new Date(curr.lastReceived)
  //   );
  //   if (!prev[date]) {
  //     prev[date] = {
  //       date,
  //       [curr.status]: 1,
  //     };
  //   } else {
  //     prev[date][curr.status]
  //       ? (prev[date][curr.status] += 1)
  //       : (prev[date][curr.status] = 1);
  //   }
  //   return prev;
  // }, {} as { [date: string]: any });
  // const chartData = Object.keys(rawChartData).map((key) => {
  //   return { date: key, ...rawChartData[key] };
  // });
  // const categoriesByStatus = data
  //   .map((alert) => alert.status)
  //   .filter(onlyUnique);

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
                className="w-full max-w-7xl max-h-[710px] transform overflow-scroll ring-tremor bg-white
                                    p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
              >
                <Flex alignItems="center" justifyContent="between">
                  <Title>History of: &quot;{data[0]?.name}&quot;</Title>
                  <Button
                    className="mt-2 bg-white border-gray-200 text-gray-500 hover:bg-gray-50 hover:border-gray-300"
                    onClick={closeModal}
                  >
                    Close
                  </Button>
                </Flex>
                {/* <LineChart
                  className="mt-6"
                  data={chartData}
                  index="date"
                  categories={categoriesByStatus}
                  yAxisWidth={40}
                /> */}
                <AlertTable data={data} />
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
