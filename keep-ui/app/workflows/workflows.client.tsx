'use client';

import { useState } from "react";
import useSWR from "swr";
import { Callout } from "@tremor/react";
import { ExclamationCircleIcon, ClipboardIcon } from "@heroicons/react/24/outline";
import { useSession } from "../../utils/customAuth";
import { fetcher } from "../../utils/fetcher";
import { Workflow } from "./models";
import { getApiURL } from "../../utils/apiUrl";
import Loading from "../loading";
import Image from 'next/image';
import { PlayIcon, ArrowDownTrayIcon, EyeIcon } from "@heroicons/react/24/outline";
import React from "react";
import DragAndDrop from "./dragndrop";
import NoWorkflows from "./noworfklows";
import { useRouter } from 'next/navigation'

function copyToClipboard(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}


function WorkflowTile({ workflow }: { workflow: Workflow }) {
  // Create a set to keep track of unique providers
  const uniqueProviders = new Set();
  const router = useRouter();

  const handleTileClick = () => {
    router.push(`/workflows/${workflow.id}`);
  };


  // Prepare the unique list of providers' icons
  const icons = [...workflow.providers].map((provider) => {
    const providerType = provider.type;
    if (!uniqueProviders.has(providerType)) {
      uniqueProviders.add(providerType);
      return (
        <Image
          className={`inline-block rounded-full ${uniqueProviders.size === 1 ? "" : "-ml-2"}`}
          key={provider.id}
          alt={providerType}
          height={24}
          width={24}
          title={providerType}
          src={`/icons/${providerType}-icon.png`}
        />
      );
    }
    return null; // Return null for duplicated providers
  });

  return (
    <div className="border border-gray-300 p-4 rounded-lg relative hover:bg-gray-100 cursor-pointer" onClick={handleTileClick}>
      <div className="flex items-center justify-between mb-2">
        <h2 className="font-semibold text-lg">{workflow.description}</h2>
        <div className="flex space-x-2">
          <button
            className="p-1 rounded-full hover:bg-gray-200"
            onClick={() => {
              // Handle the run action here
            }}
            title="Run Workflow"
          >
            <PlayIcon className="h-6 w-6 text-purple-600" />
          </button>
          <button
            className="p-1 rounded-full hover:bg-gray-200"
            onClick={() => {
              // Handle the download action here
            }}
            title="Download Workflow"
          >
            <ArrowDownTrayIcon className="h-6 w-6 text-purple-600" />
          </button>
          <button
            className="p-1 rounded-full hover:bg-gray-200"
            onClick={() => {
              // Handle the view action here
            }}
            title="View Workflow"
          >
            <EyeIcon className="h-6 w-6 text-purple-600" />
          </button>
        </div>
      </div>
      <div className="flex">{icons}</div>
      <p>Created by: {workflow.created_by}</p>
      <p>Created at: {workflow.creation_time}</p>
      <p>Triggers: </p>
      <p>Last execution time: {workflow.interval}</p>
      <p>Last execution status: </p>
    </div>
  );
}


export default function WorkflowsPage() {
  const apiUrl = getApiURL();
  const [selectedStatus, setSelectedStatus] = useState<string[]>([]);
  const { data: session, status, update } = useSession();
  const [copied, setCopied] = useState(false);
  const [isDragActive, setIsDragActive] = useState(false);

  const copyCurlCommand = () => {
    copyToClipboard(`curl -X POST ...\n...`);
    setCopied(true);
  };


  const { data, error, isLoading } = useSWR<Workflow[]>(
      `${apiUrl}/workflows`,
      (url) => fetcher(url, session?.accessToken!)
  );

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
  if (status === "loading" || isLoading || !data) return <Loading />;
  if (status === "unauthenticated") return <div>Unauthenticated...</div>;

  return (
    <div>
      <div>
        {data.length === 0 ? (
          <NoWorkflows copyCurlCommand={copyCurlCommand} />
        ) : (
          <div>
            <DragAndDrop/>
            <div className="grid grid-cols-3 gap-4 mt-10">
              {data.map((workflow) => (
                <WorkflowTile key={workflow.workflow_id} workflow={workflow} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );

}
