import { Fragment } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { AlertDto } from "@/entities/alerts/model";
import { Button, Title, Divider } from "@tremor/react";
import { IoMdClose } from "react-icons/io";
import { AlertTimeline } from "./alert-timeline";
import { useAlerts } from "@/entities/alerts/model/useAlerts";
import { TopologyMap } from "@/app/(keep)/topology/ui/map";
import { TopologySearchProvider } from "@/app/(keep)/topology/TopologySearchContext";
import {
  FieldHeader,
  SeverityLabel,
  UISeverity,
  showErrorToast,
  showSuccessToast,
} from "@/shared/ui";
import { Link } from "@/components/ui";
import { useProviders } from "@/utils/hooks/useProviders";
// feature not supposed to import other features, TODO: move alert-menu to entities or shared
import { AlertMenu } from "@/features/alerts/alert-menu";
import { useConfig } from "@/utils/hooks/useConfig";
import { DOCS_CLIPBOARD_COPY_ERROR_PATH } from "@/shared/constants";
import CollapsibleIncidentsList from "./alert-sidebar-incidents";
import {
  alertSidebarFieldsConfig,
  getEnabledFields,
  getCustomFields,
  renderCustomField,
  AlertSidebarFieldName,
} from "../lib/alertSidebarFields";

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

  const handleCopyUrl = async (alertUrl: string | undefined) => {
    if (!alertUrl) {
      showErrorToast(new Error("Alert has no URL"));
      return;
    }
    try {
      await navigator.clipboard.writeText(alertUrl);
      showSuccessToast("URL copied to clipboard");
    } catch (err) {
      showErrorToast(
        err,
        <p>
          Failed to copy URL. Please check your browser permissions.{" "}
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
                  {(() => {
                    const configuredFields = config?.ALERT_SIDEBAR_FIELDS || [];
                    const enabledFields = getEnabledFields(configuredFields);
                    const customFields = getCustomFields(configuredFields);
                    
                    const fieldRendererProps = {
                      alert,
                      providerName,
                      config,
                      handleCopyFingerprint,
                      handleCopyUrl,
                    };

                    const standardFields = enabledFields.map((fieldName) => {
                      const fieldConfig = alertSidebarFieldsConfig[fieldName];
                      
                      // Skip special fields that are rendered outside the loop
                      if (
                        fieldName === "incidents" ||
                        fieldName === "timeline" ||
                        fieldName === "relatedServices"
                      ) {
                        return null;
                      }

                      if (fieldConfig.shouldRender(alert)) {
                        return (
                          <Fragment key={fieldName}>
                            {fieldConfig.render(fieldRendererProps)}
                          </Fragment>
                        );
                      }
                      return null;
                    });

                    // Render custom fields (using dot notation paths)
                    const customFieldElements = customFields.map((fieldPath) => {
                      const rendered = renderCustomField(alert, fieldPath);
                      return rendered ? (
                        <Fragment key={fieldPath}>{rendered}</Fragment>
                      ) : null;
                    });

                    return [...standardFields, ...customFieldElements];
                  })()}
                </div>
                {config?.ALERT_SIDEBAR_FIELDS?.includes("incidents") &&
                  alert.incident_dto && (
                    <div>
                      <FieldHeader>Incidents</FieldHeader>
                      <CollapsibleIncidentsList
                        incidents={alert.incident_dto}
                      />
                    </div>
                  )}
                {config?.ALERT_SIDEBAR_FIELDS?.includes("timeline") && (
                  <AlertTimeline
                    key={auditData ? auditData.length : 1}
                    alert={alert}
                    auditData={auditData || []}
                    isLoading={isLoading}
                    onRefresh={handleRefresh}
                  />
                )}
                {config?.ALERT_SIDEBAR_FIELDS?.includes("relatedServices") && (
                  <>
                    <Title>Related Services</Title>
                    <TopologySearchProvider>
                      <TopologyMap
                        providerIds={alert.providerId ? [alert.providerId] : []}
                        services={alert.service ? [alert.service] : []}
                      />
                    </TopologySearchProvider>
                  </>
                )}
              </div>
            )}
          </Dialog.Panel>
        </Transition.Child>
      </Dialog>
    </Transition>
  );
};
