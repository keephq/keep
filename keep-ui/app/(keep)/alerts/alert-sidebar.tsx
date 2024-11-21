import { Fragment } from "react";
import Image from "next/image";
import { Dialog, Transition } from "@headlessui/react";
import { AlertDto } from "./models";
import { Button, Title, Card, Badge } from "@tremor/react";
import { IoMdClose } from "react-icons/io";
import AlertTimeline from "./alert-timeline";
import { useAlerts } from "utils/hooks/useAlerts";
import { TopologyMap } from "../topology/ui/map";
import { TopologySearchProvider } from "@/app/(keep)/topology/TopologySearchContext";

type AlertSidebarProps = {
  isOpen: boolean;
  toggle: VoidFunction;
  alert: AlertDto | null;
};

const AlertSidebar = ({ isOpen, toggle, alert }: AlertSidebarProps) => {
  const { useAlertAudit } = useAlerts();
  const {
    data: auditData,
    isLoading,
    mutate,
  } = useAlertAudit(alert?.fingerprint || "");

  const handleRefresh = async () => {
    console.log("Refresh button clicked");
    await mutate();
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog onClose={toggle}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/30 z-20" aria-hidden="true" />
        </Transition.Child>
        <Transition.Child
          as={Fragment}
          enter="transition ease-in-out duration-300 transform"
          enterFrom="translate-x-full"
          enterTo="translate-x-0"
          leave="transition ease-in-out duration-300 transform"
          leaveFrom="translate-x-0"
          leaveTo="translate-x-full"
        >
          <Dialog.Panel className="fixed right-0 inset-y-0 w-2/4 bg-white z-30 p-6 overflow-auto flex flex-col">
            <div className="flex justify-between mb-4">
              <div>
                {/*Will add soon*/}
                {/*<AlertMenu alert={alert} presetName="feed" isInSidebar={true} />*/}
                {/*<Divider></Divider>*/}
                <Dialog.Title className="text-3xl font-bold" as={Title}>
                  Alert Details
                  <Badge className="ml-4" color="orange">
                    Beta
                  </Badge>
                </Dialog.Title>
              </div>
              <div>
                <Button onClick={toggle} variant="light">
                  <IoMdClose className="h-6 w-6 text-gray-500" />
                </Button>
              </div>
            </div>
            {alert && (
              <div className="space-y-4">
                <Card>
                  <div className="mt-4 space-y-2">
                    <p>
                      <strong>Name:</strong> {alert.name}
                    </p>
                    <p>
                      <strong>Service:</strong> {alert.service}
                    </p>
                    <p>
                      <strong>Severity:</strong> {alert.severity}
                    </p>
                    <p>
                      <Image
                        src={`/icons/${alert.source![0]}-icon.png`}
                        alt={alert.source![0]}
                        width={24}
                        height={24}
                        className="inline-block w-6 h-6"
                      />
                    </p>
                    <p>
                      <strong>Description:</strong> {alert.description}
                    </p>
                    <p>
                      <strong>Fingerprint:</strong> {alert.fingerprint}
                    </p>
                  </div>
                </Card>
                <Card className="flex-grow">
                  <AlertTimeline
                    key={auditData ? auditData.length : 1}
                    alert={alert}
                    auditData={auditData || []}
                    isLoading={isLoading}
                    onRefresh={handleRefresh}
                  />
                </Card>
                <Title>Related Services</Title>
                <TopologySearchProvider>
                  <TopologyMap
                    providerIds={alert.providerId ? [alert.providerId] : []}
                    services={alert.service ? [alert.service] : []}
                  />
                </TopologySearchProvider>
              </div>
            )}
          </Dialog.Panel>
        </Transition.Child>
      </Dialog>
    </Transition>
  );
};

export default AlertSidebar;
