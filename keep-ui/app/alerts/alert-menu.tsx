import { Menu, Transition } from "@headlessui/react";
import { Fragment, useEffect, useRef, useState } from "react";
import { Bars3Icon } from "@heroicons/react/20/solid";
import { Icon } from "@tremor/react";
import { TrashIcon } from "@radix-ui/react-icons";
import {
  ArchiveBoxIcon,
  PaperAirplaneIcon,
  PlusIcon,
} from "@heroicons/react/24/outline";
import { getSession } from "utils/customAuth";
import { getApiURL } from "utils/apiUrl";
import Link from "next/link";
import { Provider, ProviderMethod } from "app/providers/providers";
import { toast } from "react-toastify";
import { Alert } from "./models";

interface Props {
  alert: Alert;
  canOpenHistory: boolean;
  openHistory: () => void;
  provider?: Provider;
  mutate: () => void;
}

export default function AlertMenu({
  alert,
  canOpenHistory,
  openHistory,
  provider,
  mutate,
}: Props) {
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [originalContainerHeight, setOriginalContainerHeight] = useState<
    string | null
  >(null);

  const alertName = alert.name;
  const alertSource = alert.source![0];
  const pushed = alert.pushed;

  const handleMenuFocus = () => {
    setIsMenuOpen(true);
  };

  const handleMenuBlur = () => {
    setIsMenuOpen(false);
  };

  useEffect(() => {
    const container = document.querySelector(
      ".tremor-Table-root"
    ) as HTMLElement;

    if (!container) return;

    if (isMenuOpen && menuRef.current) {
      if (!originalContainerHeight) {
        // Store the original height when the menu opens
        setOriginalContainerHeight(container.style.height || "auto");
      }

      const menuBottomPosition = menuRef.current.getBoundingClientRect().bottom;
      const containerTopPosition = container.getBoundingClientRect().top;
      const containerHeight = container.clientHeight;
      const relativeMenuBottomPosition =
        menuBottomPosition - containerTopPosition;

      // If the bottom of the menu goes beyond the container's viewport, adjust the container's height
      if (relativeMenuBottomPosition > containerHeight) {
        const extraHeightNeeded = relativeMenuBottomPosition - containerHeight;
        container.style.height = `${
          containerHeight + extraHeightNeeded + 10
        }px`;
      }
    } else if (originalContainerHeight) {
      // If menu is closed, reset the container's height
      setTimeout(() => {
        container.style.height = originalContainerHeight;
        setOriginalContainerHeight(null); // Clear the stored original height for the next time
      }, 200);
    }
  }, [isMenuOpen, originalContainerHeight]);

  const onDelete = async () => {
    const confirmed = confirm(
      "Are you sure you want to delete this alert? This is irreversible."
    );
    if (confirmed) {
      const session = await getSession();
      const apiUrl = getApiURL();
      const res = await fetch(`${apiUrl}/alerts`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session!.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ alert_name: alertName }),
      });
      if (res.ok) {
        // TODO: Think about something else but this is an easy way to refresh the page
        window.location.reload();
      }
    }
  };

  const invokeMethod = async (
    provider: Provider,
    method: ProviderMethod,
    methodParams: { [key: string]: string }
  ) => {
    const session = await getSession();
    const apiUrl = getApiURL();

    // Auto populate params from the alert itself
    method.func_params?.forEach((param) => {
      if (Object.keys(alert).includes(param.name)) {
        methodParams[param.name] = alert[
          param.name as keyof typeof alert
        ] as string;
      }
    });

    try {
      const response = await fetch(
        `${apiUrl}/providers/${provider.id}/invoke/${method.func_name}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session!.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(methodParams),
        }
      );
      const response_object = await response.json();
      if (response.ok) {
        mutate();
        return response_object;
      }
      toast.error(
        `Failed to invoke "${method.name}" on ${
          provider.details.name ?? provider.id
        } due to ${response_object.detail}`,
        { position: toast.POSITION.TOP_LEFT }
      );
    } catch (e: any) {
      toast.error(
        `Failed to invoke "${method.name}" on ${
          provider.details.name ?? provider.id
        } due to ${e.message}`,
        { position: toast.POSITION.TOP_LEFT }
      );
    }
  };

  return (
    <div className="relative text-right">
      <Menu as="div" className="relative inline-block text-left">
        <div>
          <Menu.Button className="inline-flex w-full justify-center rounded-md text-sm">
            <Icon
              size="xs"
              icon={Bars3Icon}
              className="hover:bg-gray-100"
              color="gray"
            />
          </Menu.Button>
        </div>
        <Transition
          as={Fragment}
          enter="transition ease-out duration-100"
          enterFrom="transform opacity-0 scale-95"
          enterTo="transform opacity-100 scale-100"
          leave="transition ease-in duration-75"
          leaveFrom="transform opacity-100 scale-100"
          leaveTo="transform opacity-0 scale-95"
        >
          <Menu.Items
            ref={menuRef}
            onFocus={handleMenuFocus}
            onBlur={handleMenuBlur}
            className="z-50 absolute mt-2 min-w-36 origin-top-right divide-y divide-gray-100 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none"
          >
            <div className="px-1 py-1">
              <Menu.Item>
                {({ active }) => (
                  <Link
                    href={`workflows/builder?alertName=${encodeURIComponent(
                      alertName
                    )}&alertSource=${alertSource}`}
                  >
                    <button
                      disabled={!alertSource}
                      className={`${
                        active ? "bg-slate-200" : "text-gray-900"
                      } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                    >
                      <PlusIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                      Create Workflow
                    </button>
                  </Link>
                )}
              </Menu.Item>
              <Menu.Item>
                {({ active }) => (
                  <button
                    disabled={canOpenHistory}
                    onClick={openHistory}
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
            </div>
            {provider?.methods && provider?.methods?.length > 0 && (
              <div className="px-1 py-1">
                {provider.methods.map((method) => {
                  return (
                    <Menu.Item key={method.name}>
                      {({ active }) => (
                        <button
                          className={`${
                            active ? "bg-slate-200" : "text-gray-900"
                          } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                          onClick={async () =>
                            await invokeMethod(provider, method, {})
                          }
                        >
                          {/* TODO: We can probably make this icon come from the server as well */}
                          <PaperAirplaneIcon
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
                    onClick={onDelete}
                    disabled={!pushed}
                    className={`${active ? "bg-slate-200" : "text-gray-900"} ${
                      !pushed ? "text-slate-300 cursor-not-allowed" : ""
                    } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                  >
                    <TrashIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                    Delete
                  </button>
                )}
              </Menu.Item>
            </div>
          </Menu.Items>
        </Transition>
      </Menu>
    </div>
  );
}
