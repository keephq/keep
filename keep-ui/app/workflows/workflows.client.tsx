"use client";

import { useState } from "react";
import useSWR from "swr";
import { Callout } from "@tremor/react";
import {
  ExclamationCircleIcon,
} from "@heroicons/react/24/outline";
import { useSession } from "../../utils/customAuth";
import { fetcher } from "../../utils/fetcher";
import { Workflow } from "./models";
import { getApiURL } from "../../utils/apiUrl";
import Loading from "../loading";
import React from "react";
import DragAndDrop from "./dragndrop";
import NoWorkflows from "./noworfklows";
import WorkflowTile from "./workflow-tile";


function copyToClipboard(text: string) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}



export default function WorkflowsPage() {
  const apiUrl = getApiURL();
  const { data: session, status, update } = useSession();
  const [copied, setCopied] = useState(false);

  const copyCurlCommand = () => {
    copyToClipboard(`curl -X POST ...\n...`);
    setCopied(true);
  };

  // Only fetch data when the user is authenticated
  const { data, error, isLoading } = useSWR<Workflow[]>(
    status === "authenticated" ? `${apiUrl}/workflows` : null,
    (url) => fetcher(url, session?.accessToken!)
  );

  if (isLoading || !data) return <Loading />;

  if (error) {
    return (
      <Callout
        className="mt-4"
        title="Error"
        icon={ExclamationCircleIcon}
        color="rose"
      >
        Failed to load workflows
      </Callout>
    );
  }

  return (
    <div>
      <div>
        {data.length === 0 ? (
          <NoWorkflows copyCurlCommand={copyCurlCommand} />
        ) : (
          <div>
            <DragAndDrop />
            <div className="grid grid-cols-3 gap-4 mt-10">
              {data.map((workflow) => (
                <WorkflowTile key={workflow.id} workflow={workflow} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
