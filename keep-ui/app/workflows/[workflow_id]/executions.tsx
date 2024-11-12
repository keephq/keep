"use client";
import { Callout, Card } from "@tremor/react";
import React, { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { ExclamationCircleIcon } from "@heroicons/react/24/outline";
import Loading from "app/loading";
import { useRouter } from "next/navigation";
import { Workflow } from "../models";
import SideNavBar from "./side-nav-bar";
import useSWR from "swr";
import { fetcher } from "@/utils/fetcher";
import BuilderModalContent from "../builder/builder-modal";
import PageClient from "../builder/page.client";
import { useApiUrl } from "@/utils/hooks/useConfig";
import WorkflowOverview from "./workflow-overview";

export default function WorkflowDetailPage({
  params,
}: {
  params: { workflow_id: string };
}) {
  const router = useRouter();
  const { data: session, status } = useSession();
  const [navlink, setNavLink] = useState("overview");

  const apiUrl = useApiUrl();

  const {
    data: workflow,
    isLoading,
    error,
  } = useSWR<Partial<Workflow>>(
    () => (session ? `${apiUrl}/workflows/${params.workflow_id}` : null),
    (url: string) => fetcher(url, session?.accessToken)
  );

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/signin");
    }
  }, [status, router]);

  // Render loading state if session is loading
  // If the user is unauthenticated, display a loading state until the side effect is processed; after that, it will automatically redirect.
  if (status === "loading" || status === "unauthenticated") return <Loading />;

  // Handle error state for fetching workflow data
  if (isLoading) return <Loading />;
  if (error) {
    return (
      <Callout
        className="mt-4"
        title="Error"
        icon={ExclamationCircleIcon}
        color="rose"
      >
        Failed to load workflow
      </Callout>
    );
  }

  if (!workflow) {
    return null;
  }

  return (
    <Card className="relative grid p-4 w-full gap-3 grid-cols-[1fr_4fr] h-full">
      <SideNavBar
        workflow={workflow}
        handleLink={setNavLink}
        navLink={navlink}
      />
      <div className="relative overflow-auto p-0.5 flex-1 flex-shrink-1">
        {navlink === "overview" && (
          <WorkflowOverview workflow_id={params.workflow_id} />
        )}
        {navlink === "builder" && (
          <div className="h-[95%]">
            <PageClient
              workflow={workflow.workflow_raw}
              workflowId={workflow.id}
            />
          </div>
        )}
        <div className="h-fit">
          {navlink === "view_yaml" && (
            <BuilderModalContent
              closeModal={() => {}}
              compiledAlert={workflow.workflow_raw!}
              id={workflow.id}
              hideCloseButton={true}
            />
          )}
        </div>
      </div>
    </Card>
  );
}
