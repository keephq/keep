import { Menu, Transition } from "@headlessui/react";
import { Fragment, useEffect, useRef, useState } from "react";
import { Bars3Icon } from "@heroicons/react/20/solid";
import { Icon } from "@tremor/react";
import { TrashIcon } from "@radix-ui/react-icons";
import {
  ArchiveBoxIcon,
  BellSlashIcon,
  PlusIcon,
} from "@heroicons/react/24/outline";
import { getSession } from "utils/customAuth";
import { getApiURL } from "utils/apiUrl";
import Link from "next/link";

interface Props {
  alertName: string;
  alertSource?: string;
  canOpenHistory: boolean;
  openHistory: () => void;
}

export default function AlertMenu({
  alertName,
  alertSource,
  canOpenHistory,
  openHistory,
}: Props) {

  const menuRef = useRef<HTMLElement | null>(null);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const handleMenuFocus = () => {
    setIsMenuOpen(true);
  };

  const handleMenuBlur = () => {
    setIsMenuOpen(false);
  };

  useEffect(() => {
    if (isMenuOpen && menuRef.current) {
        // todo find another way
        const container = document.querySelector('.tremor-Table-root');
        if (container) {
            const menuBottomPosition = menuRef.current.getBoundingClientRect().bottom;
            const containerTopPosition = container.getBoundingClientRect().top;
            const containerHeight = container.clientHeight;
            const relativeMenuBottomPosition = menuBottomPosition - containerTopPosition;

            // If the bottom of the menu goes beyond the container's viewport, adjust the container's scroll position
            if (relativeMenuBottomPosition > containerHeight) {
                const scrollAmount = relativeMenuBottomPosition - containerHeight;
                container.scrollBy(0, scrollAmount);
            }
        }
    }
}, [isMenuOpen]);



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
          <Menu.Items ref={menuRef}  onFocus={handleMenuFocus} onBlur={handleMenuBlur} className="z-50 absolute mt-2 min-w-36 origin-top-right divide-y divide-gray-100 rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
            <div className="px-1 py-1">
              <Menu.Item>
                {({ active }) => (
                  <Link
                    href={`workflows/builder?alertName=${encodeURIComponent(alertName)}&alertSource=${alertSource}`}
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
                    disabled={true}
                    className={`${
                      active ? "bg-slate-200" : "text-gray-900"
                    } group flex w-full items-center rounded-md px-2 py-2 text-xs text-slate-300 cursor-not-allowed`}
                  >
                    <BellSlashIcon
                      className="mr-2 h-4 w-4"
                      aria-hidden="true"
                    />
                    Silence
                  </button>
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
            <div className="px-1 py-1">
              <Menu.Item>
                {({ active }) => (
                  <button
                    onClick={onDelete}
                    className={`${
                      active ? "bg-slate-200" : "text-gray-900"
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
