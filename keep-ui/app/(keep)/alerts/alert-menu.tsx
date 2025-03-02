import { Menu } from "@headlessui/react";
import { useCallback, useMemo, useState, useRef, useEffect } from "react";
import {
  ChevronDoubleRightIcon,
  ArchiveBoxIcon,
  PlusIcon,
  UserPlusIcon,
  PlayIcon,
  EyeIcon,
  AdjustmentsHorizontalIcon,
  ArrowTopRightOnSquareIcon,
  BookOpenIcon,
  TicketIcon,
  PencilSquareIcon,
  Cog8ToothIcon,
} from "@heroicons/react/24/outline";
import { EllipsisHorizontalIcon } from "@heroicons/react/20/solid";
import { IoNotificationsOffOutline } from "react-icons/io5";
import { Icon } from "@tremor/react";
import { ProviderMethod } from "@/shared/api/providers";
import { AlertDto } from "@/entities/alerts/model";
import { useProviders } from "utils/hooks/useProviders";
import { useAlerts } from "utils/hooks/useAlerts";
import { useRouter } from "next/navigation";
import { useApi } from "@/shared/lib/hooks/useApi";
import { DropdownMenu } from "@/shared/ui";
import { ElementType } from "react";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { clsx } from "clsx";
import { useWorkflowExecutions } from "@/utils/hooks/useWorkflowExecutions";
import { createPortal } from "react-dom";
import { ViewedAlert } from "./alert-table";
import { format } from "date-fns";

interface Props {
  alert: AlertDto;
  setNoteModalAlert?: (alert: AlertDto) => void;
  setTicketModalAlert?: (alert: AlertDto) => void;
  setRunWorkflowModalAlert?: (alert: AlertDto) => void;
  setDismissModalAlert?: (alert: AlertDto[]) => void;
  setChangeStatusAlert?: (alert: AlertDto) => void;
  presetName: string;
  isInSidebar?: boolean;
  setIsIncidentSelectorOpen?: (open: boolean) => void;
  toggleSidebar?: VoidFunction;
}

interface MenuItem {
  icon: ElementType;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  show?: boolean;
}

// Add the tooltip type
type TooltipPosition = { x: number; y: number } | null;

// Add the ImagePreviewTooltip component
const ImagePreviewTooltip = ({
  imageUrl,
  position,
}: {
  imageUrl: string;
  position: TooltipPosition;
}) => {
  if (!position) return null;

  return createPortal(
    <div
      className="absolute shadow-lg rounded border border-gray-100 z-50"
      style={{
        left: position.x,
        top: position.y,
        pointerEvents: "none",
      }}
    >
      <div className="p-1 bg-gray-200">
        {/* because we'll have to start managing every external static asset url (datadog/grafana/etc.) */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageUrl}
          alt="Preview"
          className="max-w-xs max-h-64 object-contain"
        />
      </div>
    </div>,
    document.body
  );
};

export default function AlertMenu({
  alert,
  setNoteModalAlert,
  setTicketModalAlert,
  setRunWorkflowModalAlert,
  setDismissModalAlert,
  setChangeStatusAlert,
  presetName,
  isInSidebar,
  setIsIncidentSelectorOpen,
  toggleSidebar,
}: Props) {
  const api = useApi();
  const router = useRouter();
  const { data: executions } = useWorkflowExecutions();
  const [viewedAlerts, setViewedAlerts] = useLocalStorage<ViewedAlert[]>(
    `viewed-alerts-${presetName}`,
    []
  );
  const [showActionsOnHover] = useLocalStorage("alert-action-tray-hover", true);
  const {
    data: { installed_providers: installedProviders } = {
      installed_providers: [],
    },
  } = useProviders({ revalidateOnFocus: false, revalidateOnMount: false });

  const { alertsMutator: mutate } = useAlerts();

  const {
    url,
    generatorURL,
    note,
    ticket_url: ticketUrl,
    ticket_status: ticketStatus,
    playbook_url,
    imageUrl,
  } = alert;

  const relevantWorkflowExecution = executions?.find(
    (wf) => wf.event_id === alert.event_id
  );

  const viewedAlert = viewedAlerts?.find(
    (a) => a.fingerprint === alert.fingerprint
  );

  // Add image-related state
  const [imageError, setImageError] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition>(null);
  const imageContainerRef = useRef<HTMLDivElement | null>(null);

  // Add image-related handlers
  const handleImageClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (imageUrl) {
      window.open(imageUrl, "_blank");
    }
  };

  const handleMouseEnter = () => {
    if (imageContainerRef.current && !imageError && imageUrl) {
      const rect = imageContainerRef.current.getBoundingClientRect();
      setTooltipPosition({
        x: rect.right - 150,
        y: rect.top - 150,
      });
    }
  };

  const handleMouseLeave = () => {
    setTooltipPosition(null);
  };

  // Add scroll handler
  useEffect(() => {
    const handleScroll = () => {
      if (tooltipPosition && imageContainerRef.current) {
        const rect = imageContainerRef.current.getBoundingClientRect();
        setTooltipPosition({
          x: rect.right + 10,
          y: rect.top - 150,
        });
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [tooltipPosition]);

  const openAlertPayloadModal = useCallback(() => {
    setViewedAlerts((prev) => {
      const newViewedAlerts = prev.filter(
        (a) => a.fingerprint !== alert.fingerprint
      );
      return [
        ...newViewedAlerts,
        {
          fingerprint: alert.fingerprint,
          viewedAt: new Date().toISOString(),
        },
      ];
    });
    router.replace(
      `/alerts/${presetName}?alertPayloadFingerprint=${alert.fingerprint}`,
      {
        scroll: false,
      }
    );
  }, [alert, presetName, router]);

  // Quick actions that appear in the action tray
  const quickActions = (
    <div
      className={clsx(
        "flex items-center gap-1",
        showActionsOnHover
          ? [
              "absolute right-full transition-all duration-200",
              "transform translate-x-full opacity-0",
              "group-hover:translate-x-[-0.5rem] group-hover:opacity-100",
            ]
          : "opacity-100"
      )}
    >
      <div
        className="DropdownMenuButton group text-gray-500 leading-none flex items-center justify-center"
        onClick={openAlertPayloadModal}
      >
        <Icon
          icon={EyeIcon}
          className={clsx(
            "w-4 h-4 object-cover rounded prevent-row-click text-gray-500",
            viewedAlert ? "text-orange-400" : ""
          )}
          tooltip={
            viewedAlert &&
            `Viewed ${format(
              new Date(viewedAlert.viewedAt),
              "MMM d, yyyy HH:mm"
            )}`
          }
        />
      </div>

      {imageUrl && !imageError && (
        <div
          ref={imageContainerRef}
          className="DropdownMenuButton group text-gray-500"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          onClick={handleImageClick}
          title="View Image"
        >
          {/* because we'll have to start managing every external static asset url (datadog/grafana/etc.) */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt="Preview"
            className="h-4 w-4 object-cover rounded prevent-row-click max-w-none"
            onError={() => setImageError(true)}
          />
        </div>
      )}
      {(url ?? generatorURL) && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            window.open(url || generatorURL, "_blank");
          }}
          className="DropdownMenuButton group text-gray-500 leading-none flex items-center justify-center"
          title="Open Original Alert"
        >
          <Icon
            icon={ArrowTopRightOnSquareIcon}
            className="w-4 h-4 text-gray-500"
          />
        </button>
      )}
      {setTicketModalAlert && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (!ticketUrl && setTicketModalAlert) {
              setTicketModalAlert(alert);
            } else {
              window.open(ticketUrl, "_blank");
            }
          }}
          className="DropdownMenuButton group text-gray-500 leading-none flex items-center justify-center"
          title={
            ticketUrl
              ? `Ticket Assigned ${
                  ticketStatus ? `(status: ${ticketStatus})` : ""
                }`
              : "Click to assign Ticket"
          }
        >
          <Icon
            icon={TicketIcon}
            className={`w-4 h-4 ${
              ticketUrl ? "text-green-500" : "text-gray-500"
            }`}
          />
        </button>
      )}
      {playbook_url && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            window.open(playbook_url, "_blank");
          }}
          className="DropdownMenuButton group text-gray-500 leading-none flex items-center justify-center"
          title="View Playbook"
        >
          <Icon icon={BookOpenIcon} className="w-4 h-4 text-gray-500" />
        </button>
      )}
      {setNoteModalAlert && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setNoteModalAlert(alert);
          }}
          className="DropdownMenuButton group text-gray-500 leading-none flex items-center justify-center"
          title="Add/Edit Note"
        >
          <Icon
            icon={PencilSquareIcon}
            className={`w-4 h-4 ${note ? "text-green-500" : "text-gray-500"}`}
          />
        </button>
      )}
      {relevantWorkflowExecution && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            router.push(
              `/workflows/${relevantWorkflowExecution.workflow_id}/runs/${relevantWorkflowExecution.workflow_execution_id}`
            );
          }}
          className="DropdownMenuButton group text-gray-500 leading-none flex items-center justify-center"
          title={`Workflow ${relevantWorkflowExecution.workflow_status}`}
        >
          <Icon
            icon={Cog8ToothIcon}
            className={`w-4 h-4 ${
              relevantWorkflowExecution.workflow_status === "success"
                ? "text-green-500"
                : relevantWorkflowExecution.workflow_status === "error"
                ? "text-red-500"
                : "text-gray-500"
            }`}
          />
        </button>
      )}
    </div>
  );

  const fingerprint = alert.fingerprint;

  const provider = installedProviders.find((p) => p.type === alert.source[0]);

  const onDismiss = useCallback(async () => {
    setDismissModalAlert?.([alert]);
  }, [alert, setDismissModalAlert]);

  const callAssignEndpoint = useCallback(
    async (unassign: boolean = false) => {
      if (
        confirm(
          "After assigning this alert to yourself, you won't be able to unassign it until someone else assigns it to himself. Are you sure you want to continue?"
        )
      ) {
        const lastReceived =
          typeof alert.lastReceived === "string"
            ? alert.lastReceived
            : alert.lastReceived.toISOString();
        await api.post(`/alerts/${fingerprint}/assign/${lastReceived}`);
        await mutate();
      }
    },
    [alert, fingerprint, api, mutate]
  );

  const isMethodEnabled = useCallback(
    (method: ProviderMethod) => {
      if (provider) {
        return method.scopes.every(
          (scope) => provider.validatedScopes[scope] === true
        );
      }

      return false;
    },
    [provider]
  );

  const openMethodModal = useCallback(
    (method: ProviderMethod) => {
      router.replace(
        `/alerts/${presetName}?methodName=${method.name}&providerId=${
          provider!.id
        }&alertFingerprint=${alert.fingerprint}`,
        {
          scroll: false,
        }
      );
    },
    [alert, presetName, provider, router]
  );

  const canAssign = true; // TODO: keep track of assignments for auditing

  const menuItems = useMemo<MenuItem[]>(
    () => [
      {
        icon: PlayIcon,
        label: "Run Workflow",
        onClick: () => setRunWorkflowModalAlert?.(alert),
      },
      {
        icon: PlusIcon,
        label: "Workflow",
        onClick: () =>
          router.push(
            `/workflows/builder?alertName=${encodeURIComponent(
              alert.name
            )}&alertSource=${alert.source![0]}`
          ),
        show: !isInSidebar,
      },
      {
        icon: ArchiveBoxIcon,
        label: "History",
        onClick: () =>
          router.replace(
            `/alerts/${presetName}?fingerprint=${alert.fingerprint}`,
            { scroll: false }
          ),
      },
      {
        icon: AdjustmentsHorizontalIcon,
        label: "Enrich",
        onClick: () =>
          router.replace(
            `/alerts/${presetName}?alertPayloadFingerprint=${alert.fingerprint}&enrich=true`
          ),
      },
      {
        icon: UserPlusIcon,
        label: "Self-Assign",
        onClick: () => callAssignEndpoint(),
        show: canAssign,
      },
      {
        icon: EyeIcon,
        label: "View Alert",
        onClick: openAlertPayloadModal,
      },
      ...(provider?.methods?.map((method) => ({
        icon: (props: any) => (
          <DynamicImageProviderIcon
            providerType={provider.type}
            {...props}
            height="16"
            width="16"
          />
        ),
        label: method.name,
        onClick: () => openMethodModal(method),
        disabled: !isMethodEnabled(method),
      })) ?? []),
      {
        icon: IoNotificationsOffOutline,
        label: alert.dismissed ? "Restore" : "Dismiss",
        onClick: onDismiss,
      },
      {
        icon: ChevronDoubleRightIcon,
        label: "Change Status",
        onClick: () => setChangeStatusAlert?.(alert),
      },
      {
        icon: PlusIcon,
        label: "Correlate Incident",
        onClick: () => setIsIncidentSelectorOpen?.(true),
        show: !!setIsIncidentSelectorOpen,
      },
    ],
    [
      isInSidebar,
      canAssign,
      openAlertPayloadModal,
      provider?.methods,
      alert,
      onDismiss,
      setIsIncidentSelectorOpen,
      setRunWorkflowModalAlert,
      router,
      presetName,
      callAssignEndpoint,
      isMethodEnabled,
      openMethodModal,
      setChangeStatusAlert,
    ]
  );

  const visibleMenuItems = useMemo(
    () => menuItems.filter((item) => item.show !== false),
    [menuItems]
  );

  if (isInSidebar) {
    return (
      <Menu as="div" className="w-full">
        <div className="flex space-x-2 w-full overflow-x-scroll">
          {quickActions}
          {visibleMenuItems.map((item, index) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label + index}
                onClick={() => {
                  item.onClick();
                  toggleSidebar?.();
                }}
                disabled={item.disabled}
                className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50"
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </Menu>
    );
  }

  return (
    <div className="flex items-center justify-end relative group min-w-[2rem]">
      {quickActions}
      <DropdownMenu.Menu
        icon={EllipsisHorizontalIcon}
        label=""
        className="transition-transform duration-200"
      >
        {visibleMenuItems.map((item, index) => (
          <DropdownMenu.Item
            key={item.label + index}
            icon={item.icon}
            label={item.label}
            onClick={item.onClick}
            disabled={item.disabled}
          />
        ))}
      </DropdownMenu.Menu>
      {tooltipPosition && imageUrl && !imageError && (
        <ImagePreviewTooltip imageUrl={imageUrl} position={tooltipPosition} />
      )}
    </div>
  );
}
