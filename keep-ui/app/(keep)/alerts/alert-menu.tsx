import { Menu } from "@headlessui/react";
import { useCallback, useMemo, useState, useRef, useEffect } from "react";
import {
  ChevronDoubleRightIcon,
  ArchiveBoxIcon,
  PlusIcon,
  UserPlusIcon,
  PlayIcon,
  AdjustmentsHorizontalIcon,
  BookOpenIcon,
  XCircleIcon,
  EyeIcon,
} from "@heroicons/react/24/outline";
import {
  CheckCircleIcon,
  ClockIcon,
  LinkIcon,
} from "@heroicons/react/20/solid";
import { IoNotificationsOffOutline, IoExpandSharp } from "react-icons/io5";
import { EllipsisHorizontalIcon } from "@heroicons/react/20/solid";
import { Icon } from "@tremor/react";
import { ProviderMethod } from "@/shared/api/providers";
import { AlertDto } from "@/entities/alerts/model";
import { useProviders } from "utils/hooks/useProviders";
import { useAlerts } from "utils/hooks/useAlerts";
import { useRouter } from "next/navigation";
import { useApi } from "@/shared/lib/hooks/useApi";
import { DropdownMenu } from "@/shared/ui";
import { ElementType } from "react";
import { Button, DynamicImageProviderIcon } from "@/components/ui";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { clsx } from "clsx";
import { useWorkflowExecutions } from "@/utils/hooks/useWorkflowExecutions";
import { ViewedAlert } from "./alert-table";
import { format } from "date-fns";
import { TbCodeDots, TbTicket } from "react-icons/tb";
import { RiStickyNoteAddLine, RiStickyNoteLine } from "react-icons/ri";
import { useAlertRowStyle } from "@/entities/alerts/model/useAlertRowStyle";
import {
  ImagePreviewTooltip,
  TooltipPosition,
} from "@/components/ui/ImagePreviewTooltip";
import { useExpandedRows } from "utils/hooks/useExpandedRows";
import { FaSlack } from "react-icons/fa";

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
  const [rowStyle] = useAlertRowStyle();
  const [viewedAlerts, setViewedAlerts] = useLocalStorage<ViewedAlert[]>(
    `viewed-alerts-${presetName}`,
    []
  );
  const [showActionsOnHover] = useLocalStorage("alert-action-tray-hover", true);
  const { isRowExpanded, toggleRowExpanded } = useExpandedRows(presetName);
  const expanded = isRowExpanded(alert.fingerprint);

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

  const updateUrl = useCallback(
    (params: { newParams?: Record<string, any>; scroll?: boolean }) => {
      const currentParams = new URLSearchParams(window.location.search);

      if (params.newParams) {
        Object.entries(params.newParams).forEach(([key, value]) =>
          currentParams.append(key, value)
        );
      }

      let newPath = `${window.location.pathname}`;

      if (currentParams.toString()) {
        newPath += `?${currentParams.toString()}`;
      }
      router.replace(newPath, {
        scroll: typeof params.scroll == "boolean" ? params.scroll : false,
      });
    },
    [router]
  );

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

    updateUrl({
      newParams: { alertPayloadFingerprint: alert.fingerprint },
    });
  }, [alert, updateUrl]);

  const actionIconButtonClassName = clsx(
    "text-gray-500 leading-none p-2 prevent-row-click hover:bg-slate-200 [&>[role='tooltip']]:z-50",
    rowStyle === "relaxed" || isInSidebar
      ? "rounded-tremor-default"
      : "rounded-none"
  );

  // check if the alert has slack_link attribute
  const slackLink = alert?.slack_link;

  // Quick actions that appear in the action tray
  // @tb: Create a dynamic component like Druids ActionTray that accepts a list of actions and renders them in a grid
  const quickActions = (
    <div
      className={clsx(
        "flex items-center",
        showActionsOnHover
          ? [
              "transition-opacity duration-100",
              "opacity-0 bg-orange-100",
              "group-hover:opacity-100",
            ]
          : "opacity-100"
      )}
    >
      <Button
        className={actionIconButtonClassName}
        onClick={openAlertPayloadModal}
        variant="light"
        icon={() => (
          <Icon
            icon={TbCodeDots}
            className={clsx(
              "w-4 h-4 object-cover rounded text-gray-500",
              viewedAlert ? "text-orange-400" : ""
            )}
          />
        )}
        tooltip={
          viewedAlert
            ? `Viewed ${format(
                new Date(viewedAlert.viewedAt),
                "MMM d, yyyy HH:mm"
              )}`
            : "View Alert Payload"
        }
      />
      {/* Expand button */}
      <Button
        className={actionIconButtonClassName}
        onClick={(e) => {
          e.stopPropagation();
          toggleRowExpanded(alert.fingerprint);
        }}
        variant="light"
        icon={() => (
          <Icon
            icon={IoExpandSharp}
            className={clsx(
              "w-4 h-4 object-cover rounded",
              expanded ? "text-orange-400" : "text-gray-500"
            )}
          />
        )}
        tooltip={expanded ? "Collapse Row" : "Expand Row"}
      />
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
      {/* Add the slack link button */}
      {slackLink && (
        <Button
          variant="light"
          onClick={(e) => {
            e.stopPropagation();
            window.open(slackLink, "_blank");
          }}
          className={actionIconButtonClassName}
          tooltip="Open in Slack"
          icon={() => <Icon icon={FaSlack} className="w-4 h-4 text-gray-500" />}
        />
      )}

      {(url ?? generatorURL) && (
        <Button
          variant="light"
          onClick={(e) => {
            e.stopPropagation();
            window.open(url || generatorURL, "_blank");
          }}
          className={actionIconButtonClassName}
          tooltip="Open Original Alert"
          icon={() => (
            <Icon icon={LinkIcon} className="w-4 h-4 text-gray-500" />
          )}
        />
      )}
      {setTicketModalAlert && (
        <Button
          variant="light"
          onClick={(e) => {
            e.stopPropagation();
            if (!ticketUrl && setTicketModalAlert) {
              setTicketModalAlert(alert);
            } else {
              window.open(ticketUrl, "_blank");
            }
          }}
          className={actionIconButtonClassName}
          tooltip={
            ticketUrl
              ? `Ticket Assigned ${
                  ticketStatus ? `(status: ${ticketStatus})` : ""
                }`
              : "Assign Ticket"
          }
          icon={() => (
            <Icon
              icon={TbTicket}
              className={`w-4 h-4 ${
                ticketUrl ? "text-green-500" : "text-gray-500"
              }`}
            />
          )}
        />
      )}
      {playbook_url && (
        <Button
          variant="light"
          onClick={(e) => {
            e.stopPropagation();
            window.open(playbook_url, "_blank");
          }}
          className={actionIconButtonClassName}
          tooltip="View Playbook"
          icon={() => (
            <Icon icon={BookOpenIcon} className="w-4 h-4 text-gray-500" />
          )}
        />
      )}
      {setNoteModalAlert && (
        <Button
          variant="light"
          onClick={(e) => {
            e.stopPropagation();
            setNoteModalAlert(alert);
          }}
          className={actionIconButtonClassName}
          tooltip={note ? "Edit Note" : "Add Note"}
          icon={() => (
            <Icon
              icon={note ? RiStickyNoteLine : RiStickyNoteAddLine}
              className={`w-4 h-4 ${note ? "text-green-500" : "text-gray-500"}`}
            />
          )}
        />
      )}
      {relevantWorkflowExecution && (
        <Button
          variant="light"
          onClick={(e) => {
            e.stopPropagation();
            window.open(
              `/workflows/${relevantWorkflowExecution.workflow_id}/runs/${relevantWorkflowExecution.workflow_execution_id}`,
              "_blank"
            );
          }}
          className={actionIconButtonClassName}
          tooltip={`Workflow ${
            relevantWorkflowExecution.workflow_status
          } at ${format(
            new Date(relevantWorkflowExecution.workflow_started),
            "MMM d, yyyy HH:mm"
          )}`}
          icon={() => (
            <Icon
              icon={
                relevantWorkflowExecution.workflow_status === "success"
                  ? CheckCircleIcon
                  : relevantWorkflowExecution.workflow_status === "error"
                  ? XCircleIcon
                  : ClockIcon
              }
              className={`w-4 h-4 ${
                relevantWorkflowExecution.workflow_status === "success"
                  ? "text-green-500"
                  : relevantWorkflowExecution.workflow_status === "error"
                  ? "text-red-500"
                  : "text-gray-500"
              }`}
            />
          )}
        />
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
      updateUrl({
        newParams: {
          methodName: method.name,
          providerId: provider!.id,
          alertFingerprint: alert.fingerprint,
        },
        scroll: false,
      });
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
          updateUrl({ newParams: { fingerprint: alert.fingerprint } }),
      },
      {
        icon: AdjustmentsHorizontalIcon,
        label: "Enrich",
        onClick: () =>
          updateUrl({
            newParams: {
              alertPayloadFingerprint: alert.fingerprint,
              enrich: true,
            },
          }),
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
            src={`/icons/${provider.type}-icon.png`}
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
        <div className="flex gap-2 w-full flex-wrap">
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
                className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-50 rounded-tremor-default"
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
    <div className="flex items-center justify-end relative group">
      {quickActions}
      <DropdownMenu.Menu
        icon={EllipsisHorizontalIcon}
        iconClassName={rowStyle !== "relaxed" ? "!rounded-none" : undefined}
        label=""
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
