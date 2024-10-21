"use client";
import { Menu, Transition, Portal } from "@headlessui/react";
import { Fragment, useState } from "react";
import { Bars3Icon } from "@heroicons/react/20/solid";
import { Icon } from "@tremor/react";
import { TrashIcon } from "@radix-ui/react-icons";
import { getSession } from "next-auth/react";
import { useApiUrl } from "utils/hooks/useConfig";
import { User } from "../models";
import { User as AuthUser } from "next-auth";
import { mutate } from "swr";
import { useFloating } from "@floating-ui/react";

interface Props {
  user: User;
  currentUser?: AuthUser;
}

export default function UsersMenu({ user, currentUser }: Props) {
  const { refs, x, y } = useFloating();
  const apiUrl = useApiUrl();

  const onDelete = async () => {
    const confirmed = confirm(
      "Are you sure you want to delete this user? This is irreversible."
    );
    if (confirmed) {
      const session = await getSession();

      const res = await fetch(`${apiUrl}/users/${user.email}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session!.accessToken}`,
          "Content-Type": "application/json",
        },
      });
      if (res.ok) {
        mutate(`${apiUrl}/users`);
      }
    }
  };

  return (
    <Menu>
      {({ open }) => (
        <>
          <Menu.Button ref={refs.setReference}>
            <Icon icon={Bars3Icon} className="hover:bg-gray-100" color="gray" />
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
                          disabled={currentUser?.email === user.email}
                          onClick={onDelete}
                          className={`${
                            active ? "bg-slate-200" : "text-gray-900"
                          } group flex w-full items-center rounded-md px-2 py-2 text-sm ${
                            currentUser?.email === user.email
                              ? "text-slate-300 cursor-not-allowed"
                              : ""
                          }`}
                        >
                          <TrashIcon
                            className="mr-2 h-4 w-4"
                            aria-hidden="true"
                          />
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
