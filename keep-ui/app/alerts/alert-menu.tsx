import { Menu, Portal, Transition } from "@headlessui/react";
import { Fragment, useState } from "react";
import { Icon } from "@tremor/react";
import {
  ArchiveBoxIcon,
  EllipsisHorizontalIcon,
  PlusIcon,
  TrashIcon,
  UserPlusIcon,
  PlayIcon,
  EyeIcon
} from "@heroicons/react/24/outline";
import { IoNotificationsOffOutline } from "react-icons/io5";

import { useSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import Link from "next/link";
import { ProviderMethod } from "app/providers/providers";
import { AlertDto } from "./models";
import { useFloating } from "@floating-ui/react";
import { useProviders } from "utils/hooks/useProviders";
import { useAlerts } from "utils/hooks/useAlerts";
import { useRouter } from "next/navigation";

interface Props {
  alert: AlertDto;
  isMenuOpen: boolean;
  setIsMenuOpen: (key: string) => void;
  setRunWorkflowModalAlert?: (alert: AlertDto) => void;
  setDismissModalAlert?: (alert: AlertDto) => void;
  presetName: string;
  setViewAlertModal?: (alert: AlertDto) => void;
}

export default function AlertMenu({
  alert,
  isMenuOpen,
  setIsMenuOpen,
  setRunWorkflowModalAlert,
  setDismissModalAlert,
  presetName,
  setViewAlertModal,
}: Props) {
  const router = useRouter();

  const apiUrl = getApiURL();
  const {
    data: { installed_providers: installedProviders } = {
      installed_providers: [],
    },
  } = useProviders({ revalidateOnFocus: false, revalidateOnMount: false });

  const { useAllAlerts } = useAlerts();
  const { mutate } = useAllAlerts({ revalidateOnMount: false });

  const { data: session } = useSession();

  const { refs, x, y } = useFloating();

  const alertName = alert.name;
  const fingerprint = alert.fingerprint;
  const alertSource = alert.source![0];

  const provider = installedProviders.find((p) => p.type === alert.source[0]);

  const DynamicIcon = (props: any) => (
    <svg
      width="24px"
      height="24px"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      {...props}
    >
      {" "}
      <image
        id="image0"
        width={"24"}
        height={"24"}
        href={`/icons/${alert.source![0]}-icon.png`}
      />
    </svg>
  );

  const onDelete = async () => {
    const confirmed = confirm(
      `Are you sure you want to ${
        alert.deleted ? "restore" : "delete"
      } this alert?`
    );
    if (confirmed) {
      const body = {
        fingerprint: fingerprint,
        lastReceived: alert.lastReceived,
        restore: alert.deleted,
      };
      const res = await fetch(`${apiUrl}/alerts`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session!.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        await mutate();
      }
    }
  };

  const onDismiss = async () => {
    setDismissModalAlert?.(alert);
    await mutate();
  };

  const callAssignEndpoint = async (unassign: boolean = false) => {
    if (
      confirm(
        "After assiging this alert to yourself, you won't be able to unassign it until someone else assigns it to himself. Are you sure you want to continue?"
      )
    ) {
      const res = await fetch(
        `${apiUrl}/alerts/${fingerprint}/assign/${alert.lastReceived.toISOString()}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session!.accessToken}`,
            "Content-Type": "application/json",
          },
        }
      );
      if (res.ok) {
        await mutate();
      }
    }
  };

  const isMethodEnabled = (method: ProviderMethod) => {
    if (provider) {
      return method.scopes.every(
        (scope) => provider.validatedScopes[scope] === true
      );
    }

    return false;
  };

  const openMethodModal = (method: ProviderMethod) => {
    router.replace(
      `/alerts/${presetName}?methodName=${method.name}&providerId=${
        provider!.id
      }&alertFingerprint=${alert.fingerprint}`,
      {
        scroll: false,
      }
    );
    handleCloseMenu();
  };

  const canAssign = true; // TODO: keep track of assignments for auditing

  const handleMenuToggle = () => {
    setIsMenuOpen(alert.fingerprint);
  };

  const handleCloseMenu = () => {
    setIsMenuOpen("");
  };

  return (
    <>
      <Menu>
        <Menu.Button ref={refs.setReference} onClick={handleMenuToggle}>
          <Icon
            icon={EllipsisHorizontalIcon}
            className="hover:bg-gray-100"
            color="gray"
          />
        </Menu.Button>
        {isMenuOpen && (
          <Portal>
            {/* when menu is opened, prevent scrolling with fixed div */}
            <div
              className="fixed inset-0"
              aria-hidden="true"
              onClick={() => handleCloseMenu()}
            />
            <Transition
              as={Fragment}
              show={isMenuOpen}
              enter="transition ease-out duration-100"
              enterFrom="transform opacity-0 scale-95"
              enterTo="transform opacity-100 scale-100"
              leave="transition ease-in duration-75"
              leaveFrom="transform opacity-100 scale-100"
              leaveTo="transform opacity-0 scale-95"
            >
              <Menu.Items
                static
                ref={refs.setFloating}
                className="z-50 absolute mt-2 divide-y divide-gray-100 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none"
                style={{ left: (x ?? 0) - 50, top: y ?? 0 }}
              >
                <div className="px-1 py-1">
                  <Menu.Item>
                    {({ active }) => (
                      <button
                        className={`${
                          active ? "bg-slate-200" : "text-gray-900"
                        } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                        onClick={() => {
                          setRunWorkflowModalAlert?.(alert);
                          handleCloseMenu();
                        }}
                      >
                        <PlayIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                        Run Workflow
                      </button>
                    )}
                  </Menu.Item>
                  <Menu.Item>
                    {({ active }) => (
                      <Link
                        href={`/workflows/builder?alertName=${encodeURIComponent(
                          alertName
                        )}&alertSource=${alertSource}`}
                      >
                        <button
                          disabled={!alertSource}
                          className={`${
                            active ? "bg-slate-200" : "text-gray-900"
                          } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                        >
                          <PlusIcon
                            className="mr-2 h-4 w-4"
                            aria-hidden="true"
                          />
                          Create Workflow
                        </button>
                      </Link>
                    )}
                  </Menu.Item>
                  <Menu.Item>
                    {({ active }) => (
                      <button
                        onClick={() => {
                          router.replace(
                            `/alerts/${presetName}?fingerprint=${alert.fingerprint}`,
                            {
                              scroll: false,
                            }
                          );
                          handleCloseMenu();
                        }}
                        className={`${
                          active ? "bg-slate-200" : "text-gray-900"
                        } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                      >
                        <ArchiveBoxIcon
                          className="mr-2 h-4 w-4"
                          aria-hidden="true"
                        />
                        History
                      </button>
                    )}
                  </Menu.Item>
                  {canAssign && (
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          onClick={() => {
                            callAssignEndpoint();
                            handleCloseMenu();
                          }}
                          className={`${
                            active ? "bg-slate-200" : "text-gray-900"
                          } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                        >
                          <UserPlusIcon
                            className="mr-2 h-4 w-4"
                            aria-hidden="true"
                          />
                          Self-Assign
                        </button>
                      )}
                    </Menu.Item>
                  )}
                  {/*View the alert */}
                  <Menu.Item>
                      {({ active }) => (
                        <button
                          onClick={() => {
                            setViewAlertModal?.(alert);
                            handleCloseMenu();
                          }}
                          className={`${
                            active ? "bg-slate-200" : "text-gray-900"
                          } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                        >
                          <EyeIcon
                            className="mr-2 h-4 w-4"
                            aria-hidden="true"
                          />
                          View Alert
                        </button>
                      )}
                    </Menu.Item>
                </div>
                {provider?.methods && provider?.methods?.length > 0 && (
                  <div className="px-1 py-1">
                    {provider.methods.map((method) => {
                      const methodEnabled = isMethodEnabled(method);
                      return (
                        <Menu.Item key={method.name}>
                          {({ active }) => (
                            <button
                              className={`${
                                active ? "bg-slate-200" : "text-gray-900"
                              } ${
                                !methodEnabled
                                  ? "text-slate-300 cursor-not-allowed"
                                  : ""
                              } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                              disabled={!methodEnabled}
                              title={
                                !methodEnabled ? "Missing required scopes" : ""
                              }
                              onClick={() => {
                                openMethodModal(method);
                              }}
                            >
                              {/* TODO: We can probably make this icon come from the server as well */}
                              <DynamicIcon
                                className="mr-2 h-4 w-4"
                                aria-hidden="true"
                              />
                              {method.name}
                            </button>
                          )}
                        </Menu.Item>
                      );
                    })}
                  </div>
                )}
                <div className="px-1 py-1">
                  <Menu.Item>
                    {({ active }) => (
                      <button
                        onClick={() => {
                          onDismiss();
                          handleCloseMenu();
                        }}
                        className={`${
                          active ? "bg-slate-200" : "text-gray-900"
                        }  group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                      >
                        <IoNotificationsOffOutline
                          className="mr-2 h-4 w-4"
                          aria-hidden="true"
                        />
                        {alert.dismissed ? "Restore" : "Dismiss"}
                      </button>
                    )}
                  </Menu.Item>
                  <Menu.Item>
                    {({ active }) => (
                      <button
                        onClick={() => {
                          onDelete();
                          handleCloseMenu();
                        }}
                        className={`${
                          active ? "bg-slate-200" : "text-gray-900"
                        }  group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                      >
                        <TrashIcon
                          className="mr-2 h-4 w-4"
                          aria-hidden="true"
                        />
                        {alert.deleted ? "Undelete" : "Delete"}
                      </button>
                    )}
                  </Menu.Item>
                </div>
              </Menu.Items>
            </Transition>
          </Portal>
        )}
      </Menu>
    </>
  );
}
