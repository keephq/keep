import { Dialog, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { AlertDto } from "./models";
import { AlertTable } from "./alert-table";
import { Button, Flex, Subtitle, Title, Divider } from "@tremor/react";
import { User } from "app/settings/models";
import { User as NextUser } from "next-auth";
import AlertHistoryCharts from "./alert-history-charts";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import Loading from "app/loading";

interface Props {
  isOpen: boolean;
  closeModal: () => void;
  selectedAlert: AlertDto | null;
  users?: User[];
  currentUser: NextUser;
  accessToken?: string;
}

export function AlertHistory({
  isOpen,
  closeModal,
  selectedAlert,
  users = [],
  currentUser,
  accessToken,
}: Props) {
  const apiUrl = getApiURL();
  const url =
    selectedAlert && accessToken
      ? `${apiUrl}/alerts/${selectedAlert.fingerprint}/history?provider_id=${
          selectedAlert.providerId
        }&provider_type=${selectedAlert.source![0]}`
      : null;
  const {
    data: alerts,
    error,
    isLoading,
  } = useSWR<AlertDto[]>(
    selectedAlert && accessToken
      ? `${apiUrl}/alerts/${selectedAlert.fingerprint}/history`
      : null,
    (url) => fetcher(url, accessToken!),
    {
      revalidateOnFocus: false,
    }
  );

  if (!selectedAlert || isLoading) {
    return <></>;
  }

  if (!alerts || error) {
    return <Loading />;
  }
  alerts.forEach(
    (alert) => (alert.lastReceived = new Date(alert.lastReceived))
  );
  const lastReceivedData = alerts.map((alert) => alert.lastReceived);
  const maxLastReceived: Date = new Date(
    Math.max(...lastReceivedData.map((date) => date.getTime()))
  );
  const minLastReceived: Date = new Date(
    Math.min(...lastReceivedData.map((date) => date.getTime()))
  );

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
                    <Title>History of: {alerts[0]?.name}</Title>
                    <Subtitle>Total alerts: {alerts.length}</Subtitle>
                    <Subtitle>
                      First Occurence: {minLastReceived.toString()}
                    </Subtitle>
                    <Subtitle>
                      Last Occurence: {maxLastReceived.toString()}
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
                <AlertHistoryCharts
                  maxLastReceived={maxLastReceived}
                  minLastReceived={minLastReceived}
                  alerts={alerts}
                />
                <Divider />
                <AlertTable
                  alerts={alerts}
                  users={users}
                  currentUser={currentUser}
                  columnsToExclude={["description"]}
                />
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
