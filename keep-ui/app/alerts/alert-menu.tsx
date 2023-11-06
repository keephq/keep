import { Menu, Transition } from "@headlessui/react";
import { Fragment, useState } from "react";
import { Bars3Icon } from "@heroicons/react/20/solid";
import { Icon } from "@tremor/react";
import {
  ArchiveBoxIcon,
  PlusIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import { getSession } from "utils/customAuth";
import { getApiURL } from "utils/apiUrl";
import Link from "next/link";
import { Provider, ProviderMethod } from "app/providers/providers";
import { Alert } from "./models";
import { AlertMethodTransition } from "./alert-method-transition";

interface Props {
  alert: Alert;
  canOpenHistory: boolean;
  openHistory: () => void;
  provider?: Provider;
  mutate?: () => void;
}

export default function AlertMenu({
  alert,
  provider,
  canOpenHistory,
  openHistory,
  mutate,
}: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [method, setMethod] = useState<ProviderMethod | null>(null);
  const alertName = alert.name;
  const alertSource = alert.source![0];

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
        mutate!();
      }
    }
  };

  const isMethodEnabled = (method: ProviderMethod) => {
    return method.scopes.every(
      (scope) =>
        provider?.validatedScopes && provider.validatedScopes[scope] === true
    );
  };

  const openMethodTransition = (method: ProviderMethod) => {
    setMethod(method);
    setIsOpen(true);
  };

  return (
    <>
      <Menu as="div" className="absolute inline-block text-left">
        <Menu.Button>
          <Icon
            size="xs"
            icon={Bars3Icon}
            className="hover:bg-gray-100"
            color="gray"
          />
        </Menu.Button>
        <Transition
          as={Fragment}
          enter="transition ease-out duration-100"
          enterFrom="transform opacity-0 scale-95"
          enterTo="transform opacity-100 scale-100"
          leave="transition ease-in duration-75"
          leaveFrom="transform opacity-100 scale-100"
          leaveTo="transform opacity-0 scale-95"
        >
          <Menu.Items className="z-50 relative mt-2 min-w-36 origin-top-right divide-y divide-gray-100 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
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
                          onClick={() => openMethodTransition(method)}
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
                    onClick={onDelete}
                    className={`${active ? "bg-slate-200" : "text-gray-900"} ${
                      !alert.pushed ? "text-slate-300 cursor-not-allowed" : ""
                    } group flex w-full items-center rounded-md px-2 py-2 text-xs`}
                    disabled={!alert.pushed}
                    title={!alert.pushed ? "Cannot delete a pulled alert" : ""}
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
      {method !== null ? (
        <AlertMethodTransition
          isOpen={isOpen}
          closeModal={() => {
            setIsOpen(false);
            setMethod(null);
          }}
          method={method}
          alert={alert}
          mutate={mutate}
          provider={provider}
        />
      ) : (
        <></>
      )}
    </>
  );
}
