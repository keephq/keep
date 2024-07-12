import { Fragment } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { AlertDto } from "./models";
import { Button, Subtitle, Title, Card, Divider, TableRow, TableCell } from "@tremor/react";
import { IoMdClose } from "react-icons/io";
import AlertMenu from "./alert-menu";
import { Chrono } from "react-chrono";
import Image from "next/image";

import {
    ChevronDoubleRightIcon,
    ArchiveBoxIcon,
    EllipsisHorizontalIcon,
    PlusIcon,
    UserPlusIcon,
    PlayIcon,
    EyeIcon,
  } from "@heroicons/react/24/outline";

type AlertSidebarProps = {
  isOpen: boolean;
  toggle: VoidFunction;
  alert: AlertDto | null;
};

const mockAuditTrail = [
    { time: "2023-07-12 14:00", event: "Alert triggered", user: "System", description: "Automatic alert triggered due to anomaly detection", avatar: "/avatars/system.png", icon: <PlusIcon /> },
    { time: "2023-07-12 14:05", event: "Alert acknowledged", user: "Alice", description: "Alert acknowledged and investigation started", avatar: "", icon: <PlusIcon /> },
    { time: "2023-07-12 14:10", event: "Alert resolved", user: "Shahar", description: "Issue identified and resolved", avatar: "", icon: <PlusIcon /> },
    { time: "2023-07-12 14:20", event: "Alert re-opened", user: "Bob", description: "New information suggests the issue persists", avatar: "", icon: <PlusIcon /> },
    { time: "2023-07-12 14:30", event: "Remediation executed", user: "System", description: "Automatic remediationremediationrem ediationremediationremediationremediationremediation script executed to address the issue", avatar: "/avatars/system.png", icon: <PlusIcon /> },
  ];


const getInitials = (name: string) =>
  ((name.match(/(^\S\S?|\b\S)?/g) ?? []).join("").match(/(^\S|\S$)?/g) ?? [])
    .join("")
    .toUpperCase();

const customContent = mockAuditTrail.map((entry, index) => (
  <div key={index} className="flex items-start space-x-4 ml-6" style={{ width: '400px' }}>
    {entry.user.toLowerCase() === "system" ? (
      <Image
        src="/icons/keep-icon.png"
        alt="Keep Logo"
        width={40}
        height={40}
        className="rounded-full flex-shrink-0"
      />
    ) : entry.avatar ? (
      <Image
        src={entry.avatar}
        alt={entry.user}
        width={40}
        height={40}
        className="rounded-full flex-shrink-0"
      />
    ) : (
      <span className="relative inline-flex items-center justify-center w-10 h-10 overflow-hidden bg-orange-400 rounded-full flex-shrink-0">
        <span className="font-medium text-white text-xs">
          {getInitials(entry.user)}
        </span>
      </span>
    )}
    <div className="flex flex-col justify-center flex-grow overflow-hidden">
      <Subtitle className="text-sm text-orange-500 font-semibold whitespace-normal overflow-wrap-break-word">{entry.event}</Subtitle>
      <Subtitle className="text-xs text-gray-600 whitespace-normal overflow-wrap-break-word">{entry.description}</Subtitle>
    </div>
  </div>
));

const AlertSidebar = ({ isOpen, toggle, alert }: AlertSidebarProps) => (
  <Transition appear show={isOpen} as={Fragment}>
    <Dialog onClose={toggle}>
      <Transition.Child
        as={Fragment}
        enter="ease-out duration-300"
        enterFrom="opacity-0"
        enterTo="opacity-100"
        leave="ease-in duration-200"
        leaveFrom="opacity-100"
        leaveTo="opacity-0"
      >
        <div className="fixed inset-0 bg-black/30 z-20" aria-hidden="true" />
      </Transition.Child>
      <Transition.Child
        as={Fragment}
        enter="transition ease-in-out duration-300 transform"
        enterFrom="translate-x-full"
        enterTo="translate-x-0"
        leave="transition ease-in-out duration-300 transform"
        leaveFrom="translate-x-0"
        leaveTo="translate-x-full"
      >
        <Dialog.Panel className="fixed right-0 inset-y-0 w-3/4 bg-white z-30 p-6 overflow-auto flex flex-col">
          <div className="flex justify-between mb-4">
            <div>
              <AlertMenu alert={alert} presetName="feed" isInSidebar={true} />
              <Divider></Divider>
              <Dialog.Title className="text-3xl font-bold" as={Title}>
                Alert Details
              </Dialog.Title>
            </div>
            <div>
              <Button onClick={toggle} variant="light">
                <IoMdClose className="h-6 w-6 text-gray-500" />
              </Button>
            </div>
          </div>
          {alert && (
            <div className="space-y-4">
              <Card>
                <div className="mt-4 space-y-2">
                  <p><strong>ID:</strong> {alert.id}</p>
                  <p><strong>Name:</strong> {alert.name}</p>
                  <p><strong>Severity:</strong> {alert.severity}</p>
                  <p><strong>Source:</strong> <img src={`/icons/${alert.source![0]}-icon.png`} alt={alert.source![0]} className="inline-block w-6 h-6" /></p>
                  <p><strong>Description:</strong> {alert.description}</p>
                </div>
              </Card>
              <Card className="flex-grow">
                <Title>Timeline</Title>
                <div className="flex-grow">
                <Chrono
                    items={mockAuditTrail.map(entry => ({ title: entry.time }))}
                    hideControls
                    disableToolbar
                    borderLessCards
                    slideShow={false}
                    mode="VERTICAL"
                    theme={{
                        primary: 'orange',
                        secondary: 'rgb(255 247 237)',
                        titleColor: 'orange',
                        titleColorActive: 'orange',
                    }}
                    fontSizes={{
                        title: '.75rem',
                      }}
                    cardWidth={400}
                    cardHeight="auto"
                    classNames={{
                        card: 'hidden',
                        cardMedia: 'hidden',
                        cardSubTitle: 'hidden',
                        cardText: 'hidden',
                        cardTitle: 'hidden',
                        title: 'mb-3',
                        contentDetails: 'w-full !m-0',
                    }}
                    >
                    {customContent}
                    </Chrono>
                </div>
              </Card>
            </div>
          )}
        </Dialog.Panel>
      </Transition.Child>
    </Dialog>
  </Transition>
);

export default AlertSidebar;
