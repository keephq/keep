"use client";
import { Menu, Transition, Portal } from "@headlessui/react";
import { Fragment, useState} from "react";
import { Bars3Icon } from "@heroicons/react/20/solid";
import { Icon } from "@tremor/react";
import { TrashIcon, UpdateIcon } from "@radix-ui/react-icons";
import { getSession } from "next-auth/react";
import { getApiURL } from "utils/apiUrl";
import { User } from "./models";
import { User as AuthUser } from "next-auth";
import { mutate } from "swr";
import { useFloating } from "@floating-ui/react-dom";


interface Props {
user?: User;
  currentUser?: AuthUser;
}

export default function ApiKeysMenu({apiKeyId}: {apiKeyId: string}) {
  const { refs, x, y } = useFloating();

  const onRegenerate = async () => {
    const confirmed = confirm(
      "This action cannot be undone. This will revoke the key and generate a new one. Any further requests made with this key will fail. Make sure to update any applications that use this key."
    );

    if (confirmed) {
      const session = await getSession();
      const apiUrl = getApiURL();
      const res = await fetch(`${apiUrl}/settings/apikey`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${session!.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({'apiKeyId': apiKeyId})
      });
      if (res.ok) {
        mutate(`${apiUrl}/settings/apikeys`);
      }
    }
  };

  const onDelete = async () => {
    const confirmed = confirm(
      "This action cannot be undone. This will permanently delete the API key and any future requests using this key will fail."
    );

    if (confirmed) {
      const session = await getSession();
      const apiUrl = getApiURL();
      const res = await fetch(`${apiUrl}/settings/apikey/${apiKeyId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session!.accessToken}`,
        },
      });
      if (res.ok) {
        mutate(`${apiUrl}/settings/apikeys`);
      }
    }
  };

  return (
    <Menu>
    {({ open }) => (
      <>
        <Menu.Button ref={refs.setReference}>
          <Icon
            icon={Bars3Icon}
            className="hover:bg-gray-100"
            color="gray"
          />
        </Menu.Button>
        {open && (
          <Portal>
            <div className="fixed inset-0" aria-hidden="true" />
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
                ref={refs.setFloating}
                className="z-50 absolute mt-2 origin-top-right divide-y divide-gray-100 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none"
                style={{ left: x ?? 0, top: y ?? 0 }}
              >
                <div className="px-1 py-1">
                  <Menu.Item>
                    {({ active }) => (
                      <button
                        onClick={onRegenerate}
                        className={`${
                          active ? "bg-slate-200" : "text-gray-900"
                        } group flex w-full items-center rounded-md px-2 py-2 text-sm`}
                      >
                        <UpdateIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                       Roll key 
                      </button>
                    )}
                  </Menu.Item>
                  <Menu.Item>
                    {({ active }) => (
                      <button
                        onClick={onDelete}
                        className={`${
                          active ? "bg-slate-200" : "text-gray-900"
                        } group flex w-full items-center rounded-md px-2 py-2 text-sm`}
                      >
                        <TrashIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                        Delete
                      </button>
                    )}
                  </Menu.Item>
                </div>
              </Menu.Items>
            </Transition>
          </Portal>
        )}
      </>
    )}
  </Menu>
  );
}

