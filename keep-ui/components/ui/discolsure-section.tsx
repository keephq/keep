import { Disclosure } from "@headlessui/react";
import { IoChevronUp } from "react-icons/io5";
import { Title, Subtitle } from "@tremor/react";
import { LinkWithIcon } from "@/components/LinkWithIcon";
import React from "react";
import { IconType } from "react-icons";
import clsx from "clsx";

interface DisclosureSectionProps {
  title: string;
  activeLink: string;
  links: Array<{
    href: string;
    icon: IconType | React.ReactNode;
    label: string;
    isLink: boolean;
    handleClick?: (e: any) => void;
    newTab?: boolean;
    active?: boolean;
    key: string;
  }>;
}

export function DisclosureSection({
  title,
  links,
  activeLink,
}: DisclosureSectionProps) {
  return (
    <Disclosure as="div" className="space-y-1" defaultOpen>
      {({ open }) => (
        <>
          <Disclosure.Button className="w-full flex justify-between items-center">
            <div className="flex items-center relative group">
              <Title className="ml-2 text-gray-900 font-bold">{title}</Title>
            </div>
            <IoChevronUp
              className={clsx({ "rotate-180": open }, "mr-2 text-slate-400")}
            />
          </Disclosure.Button>
          <Disclosure.Panel
            as="ul"
            className="space-y-2 overflow-auto min-w-[max-content] py-2 pr-4"
          >
            {links.map((link, index) => {
              const CustomIcon = link.icon as IconType;
              return (
                <li key={link.key} className="w-full">
                  {link.isLink && (
                    <LinkWithIcon
                      href={link.href}
                      icon={CustomIcon}
                      target={link.newTab ? "_blank" : ""}
                      className="min-w-[max-content] px-4"
                    >
                      <Subtitle
                        onClick={link.handleClick ? link.handleClick : () => {}}
                      >
                        {link.label}
                      </Subtitle>
                    </LinkWithIcon>
                  )}
                  {!link.isLink && (
                    <div
                      className={`min-w-full px-4 text-sm cursor-pointer hover:bg-gray-100 hover:text-orange-400 rounded-md py-2.5${
                        link.key === activeLink ? " text-orange-400" : ""
                      }`}
                      onClick={link.handleClick}
                    >
                      <div className="flex gap-2">
                        <CustomIcon size={20} />
                        <Subtitle>{link.label}</Subtitle>
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
