"use client";
import { Link } from "@/components/ui";
import { ArrowRightIcon } from "@heroicons/react/16/solid";
import { Badge, Icon, Subtitle } from "@tremor/react";

export default function Layout({
  children,
  params,
}: {
  children: any;
  params: { workflow_id: string };
}) {
  return (
    <div className="flex flex-col mb-4 h-full gap-6">
      <Subtitle className="text-sm">
        <Link href="/workflows">All Workflows</Link>{" "}
        <Icon icon={ArrowRightIcon} color="gray" size="xs" /> Workflow Builder{" "}
        <Badge
          color="orange"
          size="xs"
          className="ml-1"
          tooltip="Slack us if something isn't working properly :)"
        >
          Beta
        </Badge>
      </Subtitle>
      <div className="flex-1 h-full">{children}</div>
    </div>
  );
}
