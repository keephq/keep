"use client";
import { ArrowLeftIcon } from "@radix-ui/react-icons";
import { Card, Title, Subtitle, Text, Icon, Button } from "@tremor/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MdModeEdit } from "react-icons/md";
import { useWorkflows } from "utils/hooks/useWorkflows";
import { CgArrowsExchange } from "react-icons/cg";
import { SilencedDoorbellNotification } from "@/components/icons";
import { LinkWithIcon } from "@/components/LinkWithIcon";
import { CustomPresetAlertLinks } from "@/components/navbar/CustomPresetAlertLinks";
import { Disclosure } from "@headlessui/react";
import classNames from "classnames";
import { AiOutlineSwap } from "react-icons/ai";
import { FiFilter } from "react-icons/fi";
import { IoChevronUp } from "react-icons/io5";
import { CiUser } from "react-icons/ci";
import { FaSitemap } from "react-icons/fa";




export default function Layout({
  children,
  params,
}: {
  children: any;
  params: { workflow_id: string };
}) {
  const pathname = usePathname();
  const { data: workflows } = useWorkflows();
  const workflow = workflows?.find((wf) => wf.id === params.workflow_id);
  return (
    <>
      <div className="flex items-center mb-4 max-h-full">
        <Link
          href="/workflows"
          className="flex items-center text-gray-500 hover:text-gray-700"
        >
          <ArrowLeftIcon className="h-5 w-5 mr-1" /> Back to Workflows
        </Link>
      </div>
      <Card className="relative flex p-4 w-full justify-between gap-8">

        <div className="flex flex-col gap-10 pt-6 w-1/6 top-20 p-1">
          <div className="flex-2 h-36">
            <h1 className="text-2xl truncate">{workflow && `${workflow.name}`}</h1>
            {workflow && (
              <Text clamp-lines={3}>
                <span>{workflow.description}</span>
              </Text>
            )}
          </div>
          <div className="flex-1 space-y-8">
            {workflow && <Disclosure as="div" className="space-y-1" defaultOpen>
              {({ open }) => (
                <>
                  <Disclosure.Button className="w-full flex justify-between items-center">
                    <div className="flex items-center relative group">
                      <Title className="ml-2 text-gray-900 font-bold">
                        Analyse
                      </Title>
                    </div>
                    <IoChevronUp
                      className={classNames(
                        { "rotate-180": open },
                        "mr-2 text-slate-400"
                      )}
                    />
                  </Disclosure.Button>
                  <Disclosure.Panel
                    as="ul"
                    className="space-y-2 overflow-auto min-w-[max-content] p-2 pr-4"
                  >
                    <li>
                      <LinkWithIcon
                        href={`/workflows/${params.workflow_id}`}
                        icon={AiOutlineSwap}
                      >
                        <Subtitle>Overview</Subtitle>
                      </LinkWithIcon>
                    </li>
                  </Disclosure.Panel>
                </>
              )}
            </Disclosure>}
          {workflow && <Disclosure as="div" className="space-y-1" defaultOpen>
            {({ open }) => (
              <>
                <Disclosure.Button className="w-full flex justify-between items-center">
                  <div className="flex items-center relative group">
                    <Title className="ml-2 text-gray-900 font-bold">
                      Manage
                    </Title>
                  </div>
                  <IoChevronUp
                    className={classNames(
                      { "rotate-180": open },
                      "mr-2 text-slate-400"
                    )}
                  />
                </Disclosure.Button>
                <Disclosure.Panel
                  as="ul"
                  className="space-y-2 overflow-auto min-w-[max-content] p-2 pr-4"
                >
                  <li>
                    <LinkWithIcon
                      href={`/workflows/builder/${params.workflow_id}`}
                      icon={FaSitemap}
                    >
                      <Subtitle>Workkflow builder</Subtitle>
                    </LinkWithIcon>
                  </li>
                  <li>
                    <LinkWithIcon
                      href={`/workflows/builder/${params.workflow_id}`}
                      icon={CiUser}
                    >
                      <Subtitle>Workkflow YML Definition</Subtitle>
                    </LinkWithIcon>
                  </li>
                  <li>
                    <LinkWithIcon
                      href={`/workflows/builder/${params.workflow_id}`}
                      icon={FaSitemap}
                    >
                      <Subtitle>Downloads</Subtitle>
                    </LinkWithIcon>
                  </li>
                </Disclosure.Panel>
              </>
            )}
          </Disclosure>}
          {workflow && <Disclosure as="div" defaultOpen>
            {({ open }) => (
              <>
                <Disclosure.Button className="w-full flex justify-between items-center">
                  <div className="flex items-center relative group">
                    <Title className="ml-2 text-gray-900 font-bold">
                      Learn
                    </Title>
                  </div>
                  <IoChevronUp
                    className={classNames(
                      { "rotate-180": open },
                      "mr-2 text-slate-400"
                    )}
                  />
                </Disclosure.Button>
                <Disclosure.Panel
                  as="ul"
                  className="space-y-2 overflow-auto min-w-[max-content] p-2 pr-4"
                >
                  <li>
                    <LinkWithIcon
                      href={`/workflows/builder/${params.workflow_id}`}
                      icon={FaSitemap}
                    >
                      <Subtitle>Tutorials</Subtitle>
                    </LinkWithIcon>
                  </li>
                  <li>
                    <LinkWithIcon
                      href={`/workflows/builder/${params.workflow_id}`}
                      icon={CiUser}
                    >
                      <Subtitle>Documentation</Subtitle>
                    </LinkWithIcon>
                  </li>
                </Disclosure.Panel>
              </>
            )}
          </Disclosure>}  
          </div>

        </div>
        <div className="flex-1 overflow-auto">{children}</div>
      </Card>
    </>
  );
}
