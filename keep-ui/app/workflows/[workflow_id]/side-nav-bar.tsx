import React from 'react';
import { CiUser } from 'react-icons/ci';
import { FaSitemap } from 'react-icons/fa';
import { AiOutlineSwap } from 'react-icons/ai';
import { Workflow } from '../models';
import { Text } from "@tremor/react";
import { DisclosureSection } from '@/components/ui/discolsure-section';

export default function SideNavBar({ workflow }: { workflow: Workflow }) {
  if (!workflow) return null;

  const analyseLinks = [
    { href: `/workflows/${workflow.id}`, icon: AiOutlineSwap, label: 'Overview' },
  ];

  const manageLinks = [
    { href: `/workflows/builder/${workflow.id}`, icon: FaSitemap, label: 'Workflow Builder' },
    { href: `/workflows/builder/${workflow.id}`, icon: CiUser, label: 'Workflow YML Definition' },
    { href: `/workflows/builder/${workflow.id}`, icon: FaSitemap, label: 'Downloads' },
  ];

  const learnLinks = [
    { href: `/workflows/builder/${workflow.id}`, icon: FaSitemap, label: 'Tutorials' },
    { href: `/workflows/builder/${workflow.id}`, icon: CiUser, label: 'Documentation' },
  ];

  return (
    <div className="flex flex-col gap-10 pt-6 w-1/6 top-20 p-1">
      <div className="flex-2 h-36">
        <h1 className="text-2xl truncate">{workflow.name}</h1>
        {workflow.description && (
          <Text clamp-lines={3}>
            <span>{workflow.description}</span>
          </Text>
        )}
      </div>
      <div className="flex-1 space-y-8">
        <DisclosureSection title="Analyse" links={analyseLinks} />
        <DisclosureSection title="Manage" links={manageLinks} />
        <DisclosureSection title="Learn" links={learnLinks} />
      </div>
    </div>
  );
}
