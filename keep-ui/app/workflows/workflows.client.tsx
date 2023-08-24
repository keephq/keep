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
import { PlayIcon, ArrowDownTrayIcon, EyeIcon, TrashIcon } from "@heroicons/react/24/outline";
import React from "react";
import DragAndDrop from "./dragndrop";
import NoWorkflows from "./noworfklows";
import { useRouter } from 'next/navigation'
import Link from "next/link";

function copyToClipboard(text: string) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}


function WorkflowTile({ workflow }: { workflow: Workflow }) {
  // Create a set to keep track of unique providers
  const apiUrl = getApiURL();
  const { data: session, status, update } = useSession();
  const uniqueProviders = new Set();
  const router = useRouter();

  const handleTileClick = () => {
    router.push(`/workflows/${workflow.id}`);
  };

  const handleRunClick = async (workflowId: string) => {
    try {
      const response = await fetch(`${apiUrl}/workflows/${workflowId}/run`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });

      if (response.ok) {
        // Workflow started successfully
        // You might want to handle further actions here
      } else {
        console.error("Failed to start workflow");
      }
    } catch (error) {
      console.error("An error occurred while starting workflow", error);
    }
  };


  const handleDeleteClick = async (event: React.MouseEvent<HTMLButtonElement>) => {
    try {
      event.stopPropagation();
      const response = await fetch(`${apiUrl}/workflows/${workflow.id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });

      if (response.ok) {
        // Workflow deleted successfully
        window.location.reload();
      } else {
        console.error("Failed to delete workflow");
      }
    } catch (error) {
      console.error("An error occurred while deleting workflow", error);
    }
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
            onClick={(event) => {
              event.stopPropagation();
              handleRunClick(workflow.id);
            }}
            title="Run Workflow"
          >
            <PlayIcon className="h-6 w-6 text-purple-600" />
          </button>
          <button
            className="p-1 rounded-full hover:bg-gray-200"
            onClick={handleDeleteClick}
            title="Delete Workflow"
          >
            <TrashIcon className="h-6 w-6 text-purple-600" />
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
      <p>
        Last execution time:{" "}
        {workflow.last_execution_time ? workflow.last_execution_time : "N/A"}
      </p>
      <p>
        Last execution status:{" "}
        {workflow.last_execution_status ? workflow.last_execution_status : "N/A"}
      </p>
      <p>Triggers:</p>
        {workflow.triggers.length > 0 ? (
          <div className="border border-gray-300 p-2">
            {workflow.triggers.map((trigger, index) => (
              <div key={index} className="mb-2">
                <span className="font-semibold">Trigger type: {trigger.type}</span>
                {trigger.type === "alert" && trigger.filters  ? (
                  <>
                    <br />
                    Filters:
                    {trigger.filters.map((filter, filterIndex) => (
                      <span key={filterIndex} className="mr-1">
                        <br />
                        - {filter.key}={filter.value}
                      </span>
                    ))}
                  </>
                ) : trigger.type === "interval" ? (
                  <>
                    <br />
                    Interval: <br /> - {trigger.value} seconds
                  </>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="border border-gray-300 p-2">This workflow does not have triggers yet.</p>
        )}

    <p>Providers:</p>
{workflow.providers.reduce((uniqueProviders: string[], provider) => {
  if (!uniqueProviders.includes(provider.name)) {
    uniqueProviders.push(provider.name);
    return uniqueProviders;
  }
  return uniqueProviders;
}, []).map((uniqueProviderName) => {
  const provider = workflow.providers.find(p => p.name === uniqueProviderName);
  if (!provider) return null;
  return (
    <p key={provider.id} className="mt-2">
      {provider.installed ? (
        <span className="text-green-500">- {provider.name} (installed)</span>
      ) : (
        <span>
          <span className="text-red-500">- {provider.name}</span>
          <Link
            href={{
              pathname: "/providers",
              query: {
                provider_type: provider.type,
                provider_name: provider.name,
              },
            }}
            passHref
            className="text-blue-500 underline"
            onClick={(event) => {
              event.stopPropagation();
            }}
          >
            (click to install)
          </Link>
        </span>
      )}
    </p>
  );
})}


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
            <DragAndDrop/>
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
