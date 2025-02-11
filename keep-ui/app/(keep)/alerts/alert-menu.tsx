import { Menu } from "@headlessui/react";
import { useCallback, useMemo } from "react";
import {
  ChevronDoubleRightIcon,
  ArchiveBoxIcon,
  PlusIcon,
  UserPlusIcon,
  PlayIcon,
  EyeIcon,
  AdjustmentsHorizontalIcon,
} from "@heroicons/react/24/outline";
import { EllipsisHorizontalIcon } from "@heroicons/react/20/solid";
import { IoNotificationsOffOutline } from "react-icons/io5";
import { ProviderMethod } from "@/app/(keep)/providers/providers";
import { AlertDto } from "@/entities/alerts/model";
import { useProviders } from "utils/hooks/useProviders";
import { useAlerts } from "utils/hooks/useAlerts";
import { useRouter } from "next/navigation";
import { useApi } from "@/shared/lib/hooks/useApi";
import { DropdownMenu } from "@/shared/ui";
import { ElementType } from "react";
import { DynamicImageProviderIcon } from "@/components/ui";

interface Props {
  alert: AlertDto;
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

export default function AlertMenu({
  alert,
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
  const {
    data: { installed_providers: installedProviders } = {
      installed_providers: [],
    },
  } = useProviders({ revalidateOnFocus: false, revalidateOnMount: false });

  const { alertsMutator: mutate } = useAlerts();

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

  const openAlertPayloadModal = useCallback(() => {
    router.replace(
      `/alerts/${presetName}?alertPayloadFingerprint=${alert.fingerprint}`,
      {
        scroll: false,
      }
    );
  }, [alert, presetName, router]);

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
    // For sidebar we want to show the menu items in a horizontal scrollable menu
    return (
      <Menu as="div" className="w-full">
        <div className="flex space-x-2 w-full overflow-x-scroll">
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
    <DropdownMenu.Menu icon={EllipsisHorizontalIcon} label="">
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
  );
}
