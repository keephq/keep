"use client";
import { Card, Title, Subtitle, Text, Icon } from "@tremor/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MdModeEdit } from "react-icons/md";
import { useWorkflows } from "utils/hooks/useWorkflows";

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
      <main className="p-4 md:p-10 mx-auto max-w-full">
        <div className="flex justify-between">
          <div>
            <Title>Workflow {workflow && ` - ${workflow.name}`}</Title>
            {workflow && (
              <Text>
                Description:{" "}
                <span className="font-bold">{workflow.description}</span>
              </Text>
            )}
            {pathname?.includes("runs") === false && (
              <Subtitle>List of all recent workflow executions</Subtitle>
            )}
          </div>
          <Link href={`/workflows/builder/${params.workflow_id}`}>
            <Icon
              icon={MdModeEdit}
              color="orange"
              className="hover:bg-orange-100"
              size="xl"
              tooltip="Edit Workflow"
              variant="solid"
            />
          </Link>
        </div>
        <Card className="mt-10 p-4 md:p-10 mx-auto">{children}</Card>
      </main>
    </>
  );
}
