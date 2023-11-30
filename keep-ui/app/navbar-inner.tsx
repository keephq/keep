import { Disclosure, Menu, Transition } from "@headlessui/react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import { Fragment } from "react";
import {
  Bars3Icon,
  BellAlertIcon,
  BriefcaseIcon,
  DocumentTextIcon,
  EnvelopeOpenIcon,
  PuzzlePieceIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import Link from "next/link";
import { Icon } from "@tremor/react";
import { AuthenticationType } from "utils/authenticationType";
import useSWR from "swr";
import { fetcher } from "utils/fetcher";
import { User } from "next-auth";
import { InternalConfig } from "types/internal-config";

const navigation = [
  { name: "Providers", href: "/providers", icon: PuzzlePieceIcon },
  { name: "Alerts", href: "/alerts", icon: BellAlertIcon },
  { name: "Workflows", href: "/workflows", icon: BriefcaseIcon },
  // {
  //   name: "Notifications Hub",
  //   href: "/notifications-hub",
  //   icon: EnvelopeOpenIcon,
  // },
];

function classNames(...classes: string[]) {
  return classes.filter(Boolean).join(" ");
}

const SlackLogo = (props: any) => (
  <svg
    width="800px"
    height="800px"
    viewBox="0 0 16 16"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    {...props}
  >
    <g fillRule="evenodd" clipRule="evenodd">
      <path
        fill="#E01E5A"
        d="M2.471 11.318a1.474 1.474 0 001.47-1.471v-1.47h-1.47A1.474 1.474 0 001 9.846c.001.811.659 1.469 1.47 1.47zm3.682-2.942a1.474 1.474 0 00-1.47 1.471v3.683c.002.811.66 1.468 1.47 1.47a1.474 1.474 0 001.47-1.47V9.846a1.474 1.474 0 00-1.47-1.47z"
      />
      <path
        fill="#36C5F0"
        d="M4.683 2.471c.001.811.659 1.469 1.47 1.47h1.47v-1.47A1.474 1.474 0 006.154 1a1.474 1.474 0 00-1.47 1.47zm2.94 3.682a1.474 1.474 0 00-1.47-1.47H2.47A1.474 1.474 0 001 6.153c.002.812.66 1.469 1.47 1.47h3.684a1.474 1.474 0 001.47-1.47z"
      />
      <path
        fill="#2EB67D"
        d="M9.847 7.624a1.474 1.474 0 001.47-1.47V2.47A1.474 1.474 0 009.848 1a1.474 1.474 0 00-1.47 1.47v3.684c.002.81.659 1.468 1.47 1.47zm3.682-2.941a1.474 1.474 0 00-1.47 1.47v1.47h1.47A1.474 1.474 0 0015 6.154a1.474 1.474 0 00-1.47-1.47z"
      />
      <path
        fill="#ECB22E"
        d="M8.377 9.847c.002.811.659 1.469 1.47 1.47h3.683A1.474 1.474 0 0015 9.848a1.474 1.474 0 00-1.47-1.47H9.847a1.474 1.474 0 00-1.47 1.47zm2.94 3.682a1.474 1.474 0 00-1.47-1.47h-1.47v1.47c.002.812.659 1.469 1.47 1.47a1.474 1.474 0 001.47-1.47z"
      />
    </g>
  </svg>
);

const GnipLogo = (props: any) => (
  <svg
    width="24px"
    height="24px"
    viewBox="0 0 24 24"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    {...props}
  >
    {" "}
    <image id="image0" width={"24"} height={"24"} href="/gnip.webp" />
  </svg>
);

export default function NavbarInner({ user }: { user?: User }) {
  const pathname = usePathname();
  const { data: configData } = useSWR<InternalConfig>("/api/config", fetcher);

  // Determine runtime configuration
  const authType = configData?.AUTH_TYPE;

  return (
    <Disclosure as="nav" className="bg-white shadow-sm">
      {({ open }) => (
        <>
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex h-16 justify-between">
              <div className="flex">
                <div className="flex flex-shrink-0 items-center">
                  <a href="/">
                    <Image
                      src="/keep.png"
                      alt="Keep"
                      width={36}
                      height={36}
                      priority={true}
                    />
                  </a>
                </div>
                <div className="hidden sm:-my-px sm:ml-6 sm:flex sm:space-x-8">
                  {navigation.map((item) => (
                    <Link
                      key={item.name}
                      href={item.href}
                      className={classNames(
                        pathname === item.href
                          ? "border-slate-500 text-gray-900"
                          : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300",
                        "inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
                      )}
                      aria-current={pathname === item.href ? "page" : undefined}
                    >
                      <Icon icon={item.icon} color="gray" />
                      {item.name}
                    </Link>
                  ))}
                  <Link
                    key="ctrlk"
                    href="#"
                    passHref
                    className={classNames(
                      "border-transparent text-gray-300",
                      "inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium cursor-default"
                    )}
                  >
                    (or start with ⌘K)
                  </Link>
                </div>
              </div>
              <div className="hidden sm:ml-6 sm:flex sm:items-center">
                <div className="flex items-center">
                  <a href={"https://www.gnip.io/?ref=keep"} target="_blank">
                    <Icon
                      icon={GnipLogo}
                      size="lg"
                      className="grayscale hover:grayscale-0"
                      tooltip="gniP - Reverse Ping"
                    />
                  </a>
                  <a href={"https://slack.keephq.dev/"} target="_blank">
                    <Icon
                      icon={SlackLogo}
                      size="lg"
                      className="grayscale hover:grayscale-0"
                      tooltip="Join our Slack"
                    />
                  </a>
                  <a href={"https://docs.keephq.dev/"} target="_blank">
                    <Icon
                      icon={DocumentTextIcon}
                      color="orange"
                      size="lg"
                      className="grayscale hover:grayscale-0"
                      tooltip="Documentation"
                    />
                  </a>
                </div>
                {user ? (
                  <Menu as="div" className="relative ml-3">
                    <Menu.Button className="flex rounded-full bg-white text-sm hover:ring-orange-500 hover:ring-offset-2 hover:ring-2">
                      <span className="sr-only">Open user menu</span>
                      {
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          className="h-8 w-8 rounded-full"
                          src={
                            user?.image ||
                            `https://ui-avatars.com/api/?name=${
                              user?.name ?? user?.email
                            }&background=random`
                          }
                          height={32}
                          width={32}
                          alt={`${user?.name ?? user?.email} profile picture`}
                        />
                      }
                    </Menu.Button>
                    <Transition
                      as={Fragment}
                      enter="transition ease-out duration-200"
                      enterFrom="transform opacity-0 scale-95"
                      enterTo="transform opacity-100 scale-100"
                      leave="transition ease-in duration-75"
                      leaveFrom="transform opacity-100 scale-100"
                      leaveTo="transform opacity-0 scale-95"
                    >
                      <Menu.Items className="absolute right-0 z-10 mt-2 w-48 origin-top-right rounded-md bg-white py-1 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                        <Menu.Item>
                          {({ active }) => (
                            <>
                              <a
                                className={classNames(
                                  "flex w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                )}
                                href="/settings"
                              >
                                Settings
                              </a>
                              {authType != AuthenticationType.NO_AUTH ? (
                                <button
                                  className={classNames(
                                    "flex w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                  )}
                                  onClick={() => signOut()}
                                >
                                  Sign out
                                </button>
                              ) : null}
                            </>
                          )}
                        </Menu.Item>
                      </Menu.Items>
                    </Transition>
                  </Menu>
                ) : null}
              </div>
              <div className="-mr-2 flex items-center sm:hidden">
                <Disclosure.Button className="inline-flex items-center justify-center rounded-md bg-white p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2">
                  <span className="sr-only">Open main menu</span>
                  {open ? (
                    <XMarkIcon className="block h-6 w-6" aria-hidden="true" />
                  ) : (
                    <Bars3Icon className="block h-6 w-6" aria-hidden="true" />
                  )}
                </Disclosure.Button>
              </div>
            </div>
          </div>

          <Disclosure.Panel className="sm:hidden">
            <div className="space-y-1 pt-2 pb-3">
              {navigation.map((item) => (
                <Disclosure.Button
                  key={item.name}
                  as="a"
                  href={item.href}
                  className={classNames(
                    pathname === item.href
                      ? "bg-slate-50 border-slate-500 text-slate-700"
                      : "border-transparent text-gray-600 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-800",
                    "block pl-3 pr-4 py-2 border-l-4 text-base font-medium"
                  )}
                  aria-current={pathname === item.href ? "page" : undefined}
                >
                  {item.name}
                </Disclosure.Button>
              ))}
            </div>
            <div className="border-t border-gray-200 pt-4 pb-3">
              {user ? (
                <>
                  <div className="flex items-center px-4">
                    <div className="flex-shrink-0">
                      {
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          className="h-8 w-8 rounded-full"
                          src={
                            user?.image ||
                            `https://ui-avatars.com/api/?name=${
                              user?.name ?? user?.email
                            }&background=random`
                          }
                          height={32}
                          width={32}
                          alt={`${user?.name ?? user?.email} profile picture`}
                        />
                      }
                    </div>
                    <div className="ml-3">
                      <div className="text-base font-medium text-gray-800">
                        {user.name}
                      </div>
                      <div className="text-sm font-medium text-gray-500">
                        {user.email}
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 space-y-1">
                    <a
                      className={classNames(
                        "block px-4 py-2 text-base font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-800"
                      )}
                      href="/settings"
                    >
                      Settings
                    </a>
                    {authType != AuthenticationType.NO_AUTH ? (
                      <button
                        onClick={() => signOut()}
                        className="block px-4 py-2 text-base font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-800"
                      >
                        Sign out
                      </button>
                    ) : null}
                  </div>
                </>
              ) : null}
            </div>
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
