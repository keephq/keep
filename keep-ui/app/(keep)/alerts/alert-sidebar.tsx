import { Fragment } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { AlertDto } from "@/entities/alerts/model";
import { Button, Title, Badge, Divider } from "@tremor/react";
import { IoMdClose } from "react-icons/io";
import AlertTimeline from "./alert-timeline";
import { useAlerts } from "utils/hooks/useAlerts";
import { TopologyMap } from "../topology/ui/map";
import { TopologySearchProvider } from "@/app/(keep)/topology/TopologySearchContext";
import { FieldHeader, SeverityLabel, UISeverity, Tooltip } from "@/shared/ui";
import { QuestionMarkCircleIcon } from "@heroicons/react/20/solid";
import { Link } from "@/components/ui";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useProviders } from "@/utils/hooks/useProviders";
import AlertMenu from "./alert-menu";
import { useConfig } from "@/utils/hooks/useConfig";

type AlertSidebarProps = {
  isOpen: boolean;
  toggle: VoidFunction;
  alert: AlertDto | null;
  setRunWorkflowModalAlert?: (alert: AlertDto) => void;
  setDismissModalAlert?: (alert: AlertDto[] | null) => void;
  setChangeStatusAlert?: (alert: AlertDto) => void;
  setIsIncidentSelectorOpen: (open: boolean) => void;
};

const AlertSidebar = ({
  isOpen,
  toggle,
  alert,
  setRunWorkflowModalAlert,
  setDismissModalAlert,
  setChangeStatusAlert,
  setIsIncidentSelectorOpen,
}: AlertSidebarProps) => {
  const { useAlertAudit } = useAlerts();
  const {
    data: auditData,
    isLoading,
    mutate,
  } = useAlertAudit(alert?.fingerprint || "");

  const { data: providers } = useProviders();
  const providerName =
    providers?.installed_providers.find((p) => p.id === alert?.providerId)
      ?.display_name || alert?.providerId;

  const { data: config } = useConfig();

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
              <div className="w-full">
                <AlertMenu
                  alert={alert!}
                  presetName="feed"
                  isInSidebar={true}
                  setRunWorkflowModalAlert={setRunWorkflowModalAlert}
                  setDismissModalAlert={setDismissModalAlert}
                  setChangeStatusAlert={setChangeStatusAlert}
                  setIsIncidentSelectorOpen={setIsIncidentSelectorOpen}
                />
                <Divider />
                <Dialog.Title
                  className="text-xl font-bold flex flex-col gap-2 items-start"
                  as={Title}
                >
                  {alert?.severity && (
                    <SeverityLabel
                      severity={alert.severity as unknown as UISeverity}
                    />
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
                  {alert.service && (
                    <p>
                      <FieldHeader>Service</FieldHeader>
                      <Badge size="sm" color="gray">
                        {alert.service}
                      </Badge>
                    </p>
                  )}
                  <p>
                    <FieldHeader>Source</FieldHeader>
                    <DynamicImageProviderIcon
                      src={`/icons/${alert.source![0]}-icon.png`}
                      alt={alert.source![0]}
                      width={24}
                      height={24}
                      className="inline-block w-6 h-6"
                    />
                    {providerName}
                  </p>
                  <p>
                    <FieldHeader>Description</FieldHeader>
                    <pre>{alert.description}</pre>
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
                              href={`${
                                config?.KEEP_DOCS_URL ||
                                "https://docs.keephq.dev"
                              }/providers/fingerprints#fingerprints`}
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
