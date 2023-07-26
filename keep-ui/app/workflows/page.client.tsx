"use client";
import React, { Suspense, useState } from "react";
import Image from "next/image";
import WorkflowsTable from "./workflows-table";
import {Workflow} from "./workflow-row";
import { useSession } from "../../utils/customAuth";
import useSWR from "swr";
import { fetcher } from "../../utils/fetcher";
import { getApiURL } from "../../utils/apiUrl";
import Loading from "../loading";
import { KeepApiError } from "../error";

export default function WorkflowsPage() {

  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const { data: session, status, update } = useSession();
  let shouldFetch = session?.accessToken ? true : false;

  const { data, error } = useSWR(shouldFetch? `${getApiURL()}/workflows`: null, url => {
    return fetcher(url, session?.accessToken!);
  });

  if (!data) return <Loading />;
  if (error) throw new KeepApiError(error.message, `${getApiURL()}/workflows`);

  if (data && data.workflows.length === 0) {
    // TODO: Add the processing logic for workflows here
    // The example code below is just a placeholder, you should update it accordingly

    const processedWorkflows = data.workflows.map((workflow) => {
      // Process individual workflow data and return the updated workflow object
      // Replace the following example processing with your actual processing logic
      const updatedWorkflow = {
        ...workflow,
        // Add or update properties as needed based on your processing
        owners: workflow.owners.join(', '),
        services: workflow.services.join(', '),
      };

      return updatedWorkflow;
  });

  return (
    <Suspense
      fallback={
        <Image src="/keep.gif" width={200} height={200} alt="Loading" />
      }
    >
      <WorkflowsTable workflows={workflows} />
    </Suspense>
  );
    }
