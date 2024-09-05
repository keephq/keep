import { Disclosure } from '@headlessui/react';
import classNames from 'classnames';
import { IoChevronUp } from 'react-icons/io5';
import { Title, Subtitle, Button } from "@tremor/react";
import { LinkWithIcon } from '@/components/LinkWithIcon';
import React from 'react';
import { IconType } from 'react-icons';

interface DisclosureSectionProps {
  title: string;
  links: Array<{
    href: string;
    icon: IconType | React.ReactNode;
    label: string;
    isLink: boolean;
    handleClick?: (e:any) => void;
    newTab?: boolean;
  }>;
}

export function DisclosureSection({ title, links }: DisclosureSectionProps) {
  return (
    <Disclosure as="div" className="space-y-1" defaultOpen>
      {({ open }) => (
        <>
          <Disclosure.Button className="w-full flex justify-between items-center">
            <div className="flex items-center relative group">
              <Title className="ml-2 text-gray-900 font-bold">{title}</Title>
            </div>
            <IoChevronUp
              className={classNames(
                { 'rotate-180': open },
                'mr-2 text-slate-400'
              )}
            />
          </Disclosure.Button>
          <Disclosure.Panel
            as="ul"
            className="space-y-2 overflow-auto min-w-[max-content] py-2 pr-4"
          >
            {links.map((link, index) => (
              <li key={index} className="w-full">
                <LinkWithIcon 
                href={link.isLink ? link.href : "#"}
                 icon={link.icon as IconType}
                 target= {link.newTab ? "_blank": ""}
                 className="min-w-[max-content] px-4"
                 >
                  <Subtitle onClick={link.handleClick? link.handleClick: ()=>{}}>{link.label}</Subtitle>
                </LinkWithIcon>
              </li>
            ))}
          </Disclosure.Panel>
        </>
      )}
    </Disclosure>
  );
}
