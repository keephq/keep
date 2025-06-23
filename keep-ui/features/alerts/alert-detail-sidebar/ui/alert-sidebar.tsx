import { Fragment } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { AlertDto } from "@/entities/alerts/model";
import { Button, Title, Badge, Divider } from "@tremor/react";
import { IoMdClose } from "react-icons/io";
import { AlertTimeline } from "./alert-timeline";
import { useAlerts } from "@/entities/alerts/model/useAlerts";
import { TopologyMap } from "@/app/(keep)/topology/ui/map";
import { TopologySearchProvider } from "@/app/(keep)/topology/TopologySearchContext";
import {
  FieldHeader,
  SeverityLabel,
  UISeverity,
  Tooltip,
  showErrorToast,
  showSuccessToast,
} from "@/shared/ui";
import { QuestionMarkCircleIcon } from "@heroicons/react/20/solid";
import { ClipboardDocumentIcon } from "@heroicons/react/24/outline";
import { Link } from "@/components/ui";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useProviders } from "@/utils/hooks/useProviders";
// feature not supposed to import other features, TODO: move alert-menu to entities or shared
import { AlertMenu } from "@/features/alerts/alert-menu";
import { useConfig } from "@/utils/hooks/useConfig";
import { FormattedContent } from "@/shared/ui/FormattedContent/FormattedContent";
import { IncidentDto } from "@/entities/incidents/model";
import { DOCS_CLIPBOARD_COPY_ERROR_PATH } from "@/shared/constants";

type AlertSidebarProps = {
  isOpen: boolean;
  toggle: VoidFunction;
  alert: AlertDto | null;
  setRunWorkflowModalAlert?: (alert: AlertDto) => void;
  setDismissModalAlert?: (alert: AlertDto[] | null) => void;
  setChangeStatusAlert?: (alert: AlertDto) => void;
  setIsIncidentSelectorOpen: (open: boolean) => void;
};

export const AlertSidebar = ({
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
  } = useAlertAudit(alert?.fingerprint ?? "");

  const { data: providers } = useProviders();
  const providerName =
    providers?.installed_providers.find((p) => p.id === alert?.providerId)
      ?.display_name || alert?.providerId;

  const { data: config } = useConfig();

  const handleRefresh = async () => {
    console.log("Refresh button clicked");
    await mutate();
  };

  const handleCopyFingerprint = async (alertFingerprint: string) => {
    if (!alertFingerprint) {
      showErrorToast(new Error("Alert has no fingerprint"));
      return;
    }
    try {
      await navigator.clipboard.writeText(alertFingerprint);
      showSuccessToast("Fingerprint copied to clipboard");
    } catch (err) {
      showErrorToast(
        err,
        <p>
          Failed to copy fingerprint. Please check your browser permissions.{" "}
          <Link
            target="_blank"
            href={`${config?.KEEP_DOCS_URL}${DOCS_CLIPBOARD_COPY_ERROR_PATH}`}
          >
            Learn more
          </Link>
        </p>
      );
    }
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
                <Divider className="mb-0" />
                {alert && (
                  <AlertMenu
                    alert={alert}
                    presetName="feed"
                    isInSidebar={true}
                    setRunWorkflowModalAlert={setRunWorkflowModalAlert}
                    setDismissModalAlert={setDismissModalAlert}
                    setChangeStatusAlert={setChangeStatusAlert}
                    setIsIncidentSelectorOpen={setIsIncidentSelectorOpen}
                    toggleSidebar={toggle}
                  />
                )}
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
                      providerType={alert.source![0]}
                      width={24}
                      height={24}
                      className="inline-block w-6 h-6 mr-2"
                    />
                    <span>{providerName}</span>
                  </p>
                  <p>
                    <FieldHeader>Description</FieldHeader>
                    <FormattedContent
                      content={alert.description}
                      format={alert.description_format}
                    />
                  </p>
                  <p>
                    <FieldHeader className="flex items-center gap-1">
                      Fingerprint
                      <Tooltip
                        content={
                          <>
                            Fingerprints are unique identifiers associated with
                            alert instances in Keep. Each provider declares the
                            fields fingerprints are calculated based on.{" "}
                            <Link
                              href={`${
                                config?.KEEP_DOCS_URL ||
                                "https://docs.keephq.dev"
                              }/overview/fingerprints`}
                              className="text-white"
                            >
                              Read more about it here.
                            </Link>
                          </>
                        }
                        className="z-[100]"
                      >
                        <QuestionMarkCircleIcon className="w-4 h-4" />
                      </Tooltip>
                    </FieldHeader>
                    <div className="flex items-center gap-2">
                      <span className="truncate max-w-[calc(100%-40px)] inline-block">
                        {alert.fingerprint}
                      </span>
                      <Button
                        icon={ClipboardDocumentIcon}
                        size="xs"
                        color="orange"
                        variant="light"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleCopyFingerprint(alert.fingerprint);
                        }}
                        tooltip="Copy fingerprint"
                      />
                    </div>
                  </p>
                </div>
                {alert.incident_dto && (
                  <div>
                    <FieldHeader>Incidents</FieldHeader>
                    {alert.incident_dto.map((incident: IncidentDto) => {
                      const title =
                        incident.user_generated_name ||
                        incident.ai_generated_name;
                      return (
                        <Link
                          key={incident.id}
                          href={`/incidents/${incident.id}`}
                          title={title}
                        >
                          {title}
                        </Link>
                      );
                    })}
                  </div>
                )}
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
