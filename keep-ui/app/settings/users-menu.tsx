"use client";
import { Menu, Transition } from "@headlessui/react";
import { Fragment } from "react";
import { Bars3Icon } from "@heroicons/react/20/solid";
import { Icon } from "@tremor/react";
import { TrashIcon } from "@radix-ui/react-icons";
import { getSession } from "utils/customAuth";
import { getApiURL } from "utils/apiUrl";
import { User } from "./models";
import { User as AuthUser } from "next-auth";

interface Props {
  user: User;
  currentUser?: AuthUser;
}

export default function UsersMenu({ user, currentUser }: Props) {
  const onDelete = async () => {
    const confirmed = confirm(
      "Are you sure you want to delete this alert? This is irreversible."
    );
    if (confirmed) {
      const session = await getSession();
      const apiUrl = getApiURL();
      const res = await fetch(`${apiUrl}/settings/users/${user.email}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session!.accessToken}`,
          "Content-Type": "application/json",
        },
      });
      if (res.ok) {
        // TODO: Think about something else but this is an easy way to refresh the page
        window.location.reload();
      }
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
              className="mr-2.5 hover:bg-gray-100"
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
          <Menu.Items className="z-50 fixed mt-2 w-36 origin-top-right divide-y divide-gray-100 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
            <div className="px-1 py-1">
              <Menu.Item>
                {({ active }) => (
                  <button
                    disabled={currentUser?.email === user.email}
                    onClick={onDelete}
                    className={`${
                      active ? "bg-slate-200" : "text-gray-900"
                    } group flex w-full items-center rounded-md px-2 py-2 text-xs ${
                      currentUser?.email === user.email
                        ? "text-slate-300 cursor-not-allowed"
                        : ""
                    }}`}
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
