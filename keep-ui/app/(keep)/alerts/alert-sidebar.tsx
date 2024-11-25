import { Fragment } from "react";
import Image from "next/image";
import { Dialog, Transition } from "@headlessui/react";
import { AlertDto } from "./models";
import { Button, Title, Badge } from "@tremor/react";
import { IoMdClose } from "react-icons/io";
import AlertTimeline from "./alert-timeline";
import { useAlerts } from "utils/hooks/useAlerts";
import { TopologyMap } from "../topology/ui/map";
import { TopologySearchProvider } from "@/app/(keep)/topology/TopologySearchContext";
import {
  AlertSeverityBorderIcon,
  AlertSeverityLabel,
} from "./alert-severity-border";
import { FieldHeader } from "@/shared/ui/FieldHeader";
import { QuestionMarkCircleIcon } from "@heroicons/react/20/solid";
import { Tooltip } from "@/shared/ui/Tooltip";
import { Link } from "@/components/ui";

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
                <Dialog.Title
                  className="text-xl font-bold flex flex-col gap-2 items-start"
                  as={Title}
                >
                  {alert?.severity && (
                    <AlertSeverityLabel severity={alert.severity} />
                  )}
                  {alert?.name ? alert.name : "Alert Details"}
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
                <div className="space-y-2">
                  <p>
                    <FieldHeader>Name</FieldHeader>
                    {alert.name}
                  </p>
                  <p>
                    <FieldHeader>Service</FieldHeader>
                    <Badge size="sm" color="gray">
                      {alert.service}
                    </Badge>
                  </p>
                  <p>
                    <FieldHeader>Source</FieldHeader>
                    <Image
                      src={`/icons/${alert.source![0]}-icon.png`}
                      alt={alert.source![0]}
                      width={24}
                      height={24}
                      className="inline-block w-6 h-6"
                    />
                  </p>
                  <p>
                    <FieldHeader>Description</FieldHeader>
                    {alert.description}
                  </p>
                  <p>
                    <FieldHeader className="flex items-center gap-1">
                      Fingerprint
                      <Tooltip
                        content={
                          <>
                            Fingerprints are unique identifiers associated with
                            alert instances in Keep. Every provider declares the
                            fields fingerprints are calculated upon.{" "}
                            <Link
                              href="https://docs.keephq.dev/providers/fingerprints#fingerprints"
                              className="text-white"
                            >
                              Docs
                            </Link>
                          </>
                        }
                        className="z-50"
                      >
                        <QuestionMarkCircleIcon className="w-4 h-4" />
                      </Tooltip>
                    </FieldHeader>
                    {alert.fingerprint}
                  </p>
                </div>
                <AlertTimeline
                  key={auditData ? auditData.length : 1}
                  alert={alert}
                  auditData={auditData || []}
                  isLoading={isLoading}
                  onRefresh={handleRefresh}
                />
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
