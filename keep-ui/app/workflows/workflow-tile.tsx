"use client";

import { useSession } from "../../utils/customAuth";
import { Workflow } from "./models";
import { getApiURL } from "../../utils/apiUrl";
import Image from "next/image";
import {
  ArrowDownTrayIcon,
  EyeIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import React, { useState } from "react";
import { useRouter } from "next/navigation";
import WorkflowMenu from "./workflow-menu";
import {Trigger, Provider} from "./models";
import { Button, Text } from "@tremor/react";
import ProviderForm from "app/providers/provider-form";
import SlidingPanel from "react-sliding-side-panel";
import { useFetchProviders } from "app/providers/page.client";
import { Provider as FullProvider } from 'app/providers/providers';



function WorkflowMenuSection({
  onDelete,
  onRun,
  onDownload,
  onView,
  onBuilder,
  workflow,
}: {
  onDelete: () => Promise<void>;
  onRun: (workflowId: string) => Promise<void>;
  onDownload: (event: React.MouseEvent<HTMLButtonElement>) => void;
  onView: () => void;
  onBuilder: () => void;
  workflow: Workflow;
}) {
  return (
    <div className="flex w-full items-center justify-end">
      <WorkflowMenu
        onDelete={onDelete}
        onRun={onRun}
        onDownload={onDownload}
        onView={onView}
        onBuilder={onBuilder}
      />
    </div>
  );
}

function TriggerTile({ trigger }: { trigger: Trigger }) {
  return (
    <div className="border rounded p-2 m-1 flex flex-col justify-between items-start h-full">
      <p className="text-left self-start text-xs">type: {trigger.type}</p>

      {trigger.type === "interval" && (
        <div className="flex text-left items-center justify-center h-full text-xs">
          <p>value: {trigger.value}s</p>
        </div>
      )}

      {trigger.type === "alert" && trigger.filters && (
        <div className="self-start">
          <p className="text-left self-start text-xs">filters:</p>
          {trigger.filters.map((filter, index) => (
            <p className="text-xs" key={index}>- {filter.key} = {filter.value}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function ProviderTile({ provider, onConnectClick }: { provider: FullProvider, onConnectClick: (provider: FullProvider) => void }) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="relative border rounded p-2 m-1 flex flex-col justify-between items-center h-full"
    >
      {provider.installed && (
        <div className="absolute top-0 left-0 mt-1">
          <Text color="green" className="text-xs">
            Connected
          </Text>
        </div>
      )}

      <Image
        src={`/icons/${provider.type}-icon.png`}
        width={30}
        height={30}
        alt={provider.type}
        className={`${provider.installed ? "mt-6" : "mt-6 grayscale"}`}
      />

      <div className="h-8">
        { !provider.installed && isHovered ? (
            <Button
            variant="secondary"
            size="xs"
            color="green"
            onClick={() => onConnectClick(provider)}
          >
            Connect
          </Button>
        ) : (
          <p
            className="text-tremor-default text-tremor-content dark:text-dark-tremor-content truncate capitalize"
            title={provider.id}
          >
            {provider.type}
          </p>
        )}
      </div>
    </div>
  );
}




function WorkflowTile({ workflow }: { workflow: Workflow }) {
  // Create a set to keep track of unique providers
  const apiUrl = getApiURL();
  const { data: session, status, update } = useSession();
  const router = useRouter();
  const [openPanel, setOpenPanel] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<FullProvider | null>(null);
  const [formValues, setFormValues] = useState<{ [key: string]: string }>({});
  const [formErrors, setFormErrors] = useState<{ [key: string]: string }>({});
  const { providers, installedProviders, error } = useFetchProviders();

  // Function to handle "Connect" button click
  const handleConnectClick = (providerType: string) => {
    if (status === "loading") return; // Optionally, handle loading state
    if (error) {
      console.error("An error occurred:", error);
      return;
    }

    // Find the provider with the specified type
    const providerToConnect = providers.find((p) => p.type === providerType);

    if (providerToConnect) {
      setSelectedProvider(providerToConnect);
      setOpenPanel(true);
    }
  };

  const handleConnectProvider = (provider: FullProvider) => {
    setSelectedProvider(provider);
    // prepopulate it with the name
    setFormValues({ provider_name: provider.details.name || "" });
    setOpenPanel(true);
  };

  const handleCloseModal = () => {
    setOpenPanel(false);
    setSelectedProvider(null);
    setFormValues({});
    setFormErrors({});
  };
  // Function to handle form change
  const handleFormChange = (
    updatedFormValues: Record<string, string>,
    updatedFormErrors: Record<string, string>
  ) => {
    setFormValues(updatedFormValues);
    setFormErrors(updatedFormErrors);
  };


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
        const responseData = await response.json();
        const { workflow_execution_id } = responseData;
        router.push(`/workflows/${workflowId}/runs/${workflow_execution_id}`);
      } else {
        console.error("Failed to start workflow");
      }
    } catch (error) {
      console.error("An error occurred while starting workflow", error);
    }
  };

  const handleDeleteClick = async () => {
    try {
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

  const handleConnecting = (isConnecting: boolean, isConnected: boolean) => {
    if (isConnected){
      handleCloseModal();
      // refresh the page to show the changes
      window.location.reload();
    }
  };
  const handleDownloadClick = async (
    event: React.MouseEvent<HTMLButtonElement>
  ) => {};

  const handleViewClick = async () => {
      router.push(`/builder/${workflow.id}`);
  };

  const handleBuilderClick = async () => {
    router.push(`/builder/${workflow.id}`);
  };

  const hasManualTrigger = workflow.triggers.some(
    (trigger) => trigger.type === "manual"
  );

  const workflowProvidersMap = new Map(workflow.providers.map(p => [p.type, p]));


  const uniqueProviders: FullProvider[] = Array.from(new Set(workflow.providers.map(p => p.type)))
  .map(type => {
    let fullProvider = providers.find(fp => fp.type === type) || {} as FullProvider;
    let workflowProvider = workflowProvidersMap.get(type) || {} as FullProvider;

    // Merge properties
    const mergedProvider: FullProvider = {
      ...fullProvider,
      ...workflowProvider,
      installed: workflowProvider.installed || fullProvider.installed,
      details: {
        authentication: {},
        name: (workflowProvider as Provider).name || fullProvider.id,
      },
      id: fullProvider.type,
    };

    return mergedProvider;
  })
  .filter(Boolean) as FullProvider[];



  return (
    <div className={`relative group flex flex-col justify-around  bg-white rounded-md shadow-md w-full h-auto m-2.5 `}>
        <div  className={`hover:shadow-xl hover:grayscale-0`}>
          {WorkflowMenuSection({
            onDelete: handleDeleteClick,
            onRun: handleRunClick,
            onDownload: handleDownloadClick,
            onView: handleViewClick,
            onBuilder: handleBuilderClick,
            workflow,
          })}

          <p className="text-tremor-default truncate capitalize mx-2">
            {workflow.description}
          </p>

          <p className="text-sm mx-4 mt-8  text-tremor-content dark:text-dark-tremor-content">Created by: {workflow.created_by}</p>
          <p className="text-sm mx-4 mt-2  text-tremor-content dark:text-dark-tremor-content">Created at: {workflow.creation_time}</p>
          <p className="text-sm mx-4 mt-2  text-tremor-content dark:text-dark-tremor-content">
            Last execution time: {workflow.last_execution_time ? workflow.last_execution_time : "N/A"}
          </p>
          <p className="text-sm mx-4 mt-2  text-tremor-content dark:text-dark-tremor-content">
            Last execution status: {workflow.last_execution_status ? workflow.last_execution_status : "N/A"}
          </p>
          <div
            className="bg-white rounded-lg shadow p-4 my-4 mx-4"
            style={{ minHeight: '120px' }} // Set the minimum height here
          >
            <p className="text-tremor-content dark:text-dark-tremor-content text-sm">
              Triggers:
            </p>
            <div className={`grid gap-2 ${workflow.triggers.length > 0 ? 'md:grid-cols-2 lg:grid-cols-2' : 'grid-cols-1'}`}>
              {workflow.triggers.length > 0 ? (
                workflow.triggers.map((trigger, index) => (
                  <TriggerTile key={index} trigger={trigger} />
                ))
              ) : (
                <p className="text-xs text-center mx-4 mt-2 text-tremor-content dark:text-dark-tremor-content">
                  This workflow does not have triggers yet.
                </p>
              )}
            </div>
          </div>


          <div className="bg-white rounded-lg shadow p-4 my-4 mx-4">
            <p className="text-tremor-content dark:text-dark-tremor-content text-sm">
              Providers:
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {uniqueProviders.map((provider) => (
                <ProviderTile key={provider.id} provider={provider} onConnectClick={handleConnectProvider}/>
              ))}
            </div>
        </div>
      </div>
      <SlidingPanel
        type={"right"}
        isOpen={openPanel}
        size={30}
        backdropClicked={handleCloseModal}
        panelContainerClassName="bg-white z-[2000]"
      >
        {selectedProvider && (
          <ProviderForm
          provider={selectedProvider}
          formData={formValues}
          formErrorsData={formErrors}
          onFormChange={handleFormChange}
          onConnectChange={handleConnecting}
          closeModal={handleCloseModal}
          isProviderNameDisabled={true}
        />
        )}
      </SlidingPanel>
    </div>
  );
}

export default WorkflowTile;
