"use client";
import { Link } from "@/components/ui";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import { Icon, Subtitle } from "@tremor/react";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col h-full gap-4">
      <Subtitle className="text-sm">
        <Link href="/workflows">All Workflows</Link>{" "}
        <Icon icon={ArrowRightIcon} color="gray" size="xs" /> Workflow Builder
      </Subtitle>
      <div className="flex-1 h-full">{children}</div>
    </div>
  );
}
