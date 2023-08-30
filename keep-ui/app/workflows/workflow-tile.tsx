"use client";

import { useSession } from "../../utils/customAuth";
import { Workflow } from "./models";
import { getApiURL } from "../../utils/apiUrl";
import Image from "next/image";
import React, { useState } from "react";
import { useRouter } from "next/navigation";
import WorkflowMenu from "./workflow-menu";
import { Trigger, Provider } from "./models";
import { Button, Text, Card, Title, Icon, ListItem, List } from "@tremor/react";
import ProviderForm from "app/providers/provider-form";
import SlidingPanel from "react-sliding-side-panel";
import { useFetchProviders } from "app/providers/page.client";
import { Provider as FullProvider } from "app/providers/providers";
import "./workflow-tile.css";
import {
  CheckBadgeIcon,
  CheckCircleIcon,
  XCircleIcon,
} from "@heroicons/react/24/outline";

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
    <WorkflowMenu
      onDelete={onDelete}
      onRun={onRun}
      onDownload={onDownload}
      onView={onView}
      onBuilder={onBuilder}
    />
  );
}

function TriggerTile({ trigger }: { trigger: Trigger }) {
  return (
    <ListItem>
      <span className="text-sm">{trigger.type}</span>
      {trigger.type === "manual" && (
        <span>
          <Icon icon={CheckCircleIcon} color="green" size="xs" />
        </span>
      )}
      {trigger.type === "interval" && <span>{trigger.value} seconds</span>}
      {trigger.type === "alert" && (
        <span className="text-sm text-right">
          {trigger.filters &&
            trigger.filters.map((filter, index) => (
              <>
                {filter.key} = {filter.value}
                <br />
              </>
            ))}
        </span>
      )}
    </ListItem>
  );
}

function ProviderTile({
  provider,
  onConnectClick,
}: {
  provider: FullProvider;
  onConnectClick: (provider: FullProvider) => void;
}) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`relative group flex flex-col justify-around items-center bg-white rounded-lg w-24 h-28 mt-2.5 mr-2.5 hover:grayscale-0 shadow-md hover:shadow-lg`}
      title={`${provider.details.name} (${provider.type})`}
    >
      {provider.installed ? (
        <Icon
          icon={CheckCircleIcon}
          className="absolute top-[-15px] right-[-15px]"
          color="green"
          size="sm"
          tooltip="Connected"
        />
      ) : (
        <Icon
          icon={XCircleIcon}
          className="absolute top-[-15px] right-[-15px]"
          color="red"
          size="sm"
          tooltip="Disconnected"
        />
      )}
      <Image
        src={`/icons/${provider.type}-icon.png`}
        width={30}
        height={30}
        alt={provider.type}
        className={`${
          provider.installed ? "mt-6" : "mt-6 grayscale group-hover:grayscale-0"
        }`}
      />

      <div className="h-8 w-[70px] flex justify-center">
        {!provider.installed && isHovered ? (
          <Button
            variant="secondary"
            size="xs"
            color="green"
            onClick={() => onConnectClick(provider)}
          >
            Connect
          </Button>
        ) : (
          <p className="text-tremor-default text-tremor-content dark:text-dark-tremor-content truncate">
            {provider.details.name}
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
  const [selectedProvider, setSelectedProvider] = useState<FullProvider | null>(
    null
  );
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
    if (isConnected) {
      handleCloseModal();
      // refresh the page to show the changes
      window.location.reload();
    }
  };
  const handleDownloadClick = async (
    event: React.MouseEvent<HTMLButtonElement>
  ) => {};

  const handleViewClick = async () => {
    router.push(`/workflows/${workflow.id}`);
  };

  const handleBuilderClick = async () => {
    router.push(`/builder/${workflow.id}`);
  };

  const hasManualTrigger = workflow.triggers.some(
    (trigger) => trigger.type === "manual"
  );

  const workflowProvidersMap = new Map(
    workflow.providers.map((p) => [p.type, p])
  );

  const uniqueProviders: FullProvider[] = Array.from(
    new Set(workflow.providers.map((p) => p.type))
  )
    .map((type) => {
      let fullProvider =
        providers.find((fp) => fp.type === type) || ({} as FullProvider);
      let workflowProvider =
        workflowProvidersMap.get(type) || ({} as FullProvider);

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
    <Card className="tile-basis mt-2.5">
      <div className="flex w-full justify-between items-center h-14">
        <Title>{workflow.description}</Title>
        {WorkflowMenuSection({
          onDelete: handleDeleteClick,
          onRun: handleRunClick,
          onDownload: handleDownloadClick,
          onView: handleViewClick,
          onBuilder: handleBuilderClick,
          workflow,
        })}
      </div>

      <List>
        <ListItem>
          <span>Created By</span>
          <span className="text-right">{workflow.created_by}</span>
        </ListItem>
        <ListItem>
          <span>Created At</span>
          <span className="text-right">{workflow.creation_time}</span>
        </ListItem>
        <ListItem>
          <span>Last Execution</span>
          <span className="text-right">
            {workflow.last_execution_time
              ? workflow.last_execution_time
              : "N/A"}
          </span>
        </ListItem>
        <ListItem>
          <span>Last Status</span>
          <span className="text-right">
            {workflow.last_execution_status
              ? workflow.last_execution_status
              : "N/A"}
          </span>
        </ListItem>
      </List>

      <Card className="min-h-[120px] mt-4">
        <Text>Triggers:</Text>
        {workflow.triggers.length > 0 ? (
          <List>
            {workflow.triggers.map((trigger, index) => (
              <TriggerTile key={index} trigger={trigger} />
            ))}
          </List>
        ) : (
          <p className="text-xs text-center mx-4 mt-5 text-tremor-content dark:text-dark-tremor-content">
            This workflow does not have any triggers.
          </p>
        )}
      </Card>

      <Card className="mt-2.5">
        <Text>Providers:</Text>
        <div className="flex flex-wrap justify-start">
          {uniqueProviders.map((provider) => (
            <ProviderTile
              key={provider.id}
              provider={provider}
              onConnectClick={handleConnectProvider}
            />
          ))}
        </div>
      </Card>
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
    </Card>
  );
}

export default WorkflowTile;
