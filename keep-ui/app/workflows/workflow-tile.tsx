"use client";

import { useSession } from "../../utils/customAuth";
import { Workflow } from "./models";
import { getApiURL } from "../../utils/apiUrl";
import Image from "next/image";
import React, { useState } from "react";
import { useRouter } from "next/navigation";
import WorkflowMenu from "./workflow-menu";
import Loading from "../loading";
import { Trigger, Provider } from "./models";
import {
  Button,
  Text,
  Card,
  Title,
  Icon,
  ListItem,
  List,
  Accordion,
  AccordionBody,
  AccordionHeader,
  Badge,
} from "@tremor/react";
import ProviderForm from "app/providers/provider-form";
import SlidingPanel from "react-sliding-side-panel";
import { useFetchProviders } from "app/providers/page.client";
import { Provider as FullProvider } from "app/providers/providers";
import "./workflow-tile.css";
import { CheckCircleIcon, XCircleIcon } from "@heroicons/react/24/outline";
import { QuestionMarkCircleIcon } from "@heroicons/react/20/solid";

function WorkflowMenuSection({
  onDelete,
  onRun,
  onDownload,
  onView,
  onBuilder,
  workflow,
}: {
  onDelete: () => Promise<void>;
  onRun: () => Promise<void>;
  onDownload: () => void;
  onView: () => void;
  onBuilder: () => void;
  workflow: Workflow;
}) {
  // Determine if all providers are installed
  const allProvidersInstalled = workflow.providers.every(
    (provider) => provider.installed
  );

  // Check if there is a manual trigger
  const hasManualTrigger = workflow.triggers.some(
    (trigger) => trigger.type === "manual"
  ); // Replace 'manual' with the actual value that represents a manual trigger in your data

  return (
    <WorkflowMenu
      onDelete={onDelete}
      onRun={onRun}
      onDownload={onDownload}
      onView={onView}
      onBuilder={onBuilder}
      allProvidersInstalled={allProvidersInstalled}
      hasManualTrigger={hasManualTrigger}
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
            trigger.filters.map((filter) => (
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
  const { data: session } = useSession();
  const router = useRouter();
  const [openPanel, setOpenPanel] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<FullProvider | null>(
    null
  );
  const [formValues, setFormValues] = useState<{ [key: string]: string }>({});
  const [formErrors, setFormErrors] = useState<{ [key: string]: string }>({});
  const [isRunning, setIsRunning] = useState(false);

  const { providers } = useFetchProviders();

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

  const handleRunClick = async () => {
    setIsRunning(true);
    try {
      const response = await fetch(`${apiUrl}/workflows/${workflow.id}/run`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });

      if (response.ok) {
        // Workflow started successfully
        const responseData = await response.json();
        const { workflow_execution_id } = responseData;
        setIsRunning(false);
        router.push(`/workflows/${workflow.id}/runs/${workflow_execution_id}`);
      } else {
        console.error("Failed to start workflow");
      }
    } catch (error) {
      console.error("An error occurred while starting workflow", error);
    }
    setIsRunning(false);
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
  const handleDownloadClick = async () => {
    try {
      // Use the raw workflow data directly, as it is already in YAML format
      const workflowYAML = workflow.workflow_raw;

      // Create a Blob object representing the data as a YAML file
      const blob = new Blob([workflowYAML], { type: "text/yaml" });

      // Create an anchor element with a URL object created from the Blob
      const url = window.URL.createObjectURL(blob);

      // Create a "hidden" anchor tag with the download attribute and click it
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = `${workflow.workflow_raw_id}.yaml`; // The file will be named after the workflow's id
      document.body.appendChild(a);
      a.click();

      // Release the object URL to free up resources
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("An error occurred while downloading the YAML", error);
    }
  };

  const handleViewClick = async () => {
    router.push(`/workflows/${workflow.id}`);
  };

  const handleBuilderClick = async () => {
    router.push(`/workflows/builder/${workflow.id}`);
  };

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
  const triggerTypes = workflow.triggers.map((trigger) => trigger.type);
  return (
    <div className="tile-basis mt-2.5">
      {isRunning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <Loading />
        </div>
      )}
      <Card>
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

        <Accordion className="mt-2.5">
          <AccordionHeader>
            <span className="mr-1">Triggers:</span>
            {triggerTypes.map((t) => {
              if (t === "alert") {
                let imageError = false;
                const handleImageError = () => {
                  imageError = true;
                };
                const alertSource = workflow.triggers
                  .find((w) => w.type === "alert")
                  ?.filters?.find((f) => f.key === "source")?.value;
                const DynamicIcon = (props: any) =>
                  !imageError ? (
                    <svg
                      width="24px"
                      height="24px"
                      viewBox="0 0 24 24"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      {...props}
                    >
                      {" "}
                      <image
                        id="image0"
                        width={"24"}
                        height={"24"}
                        href={`/icons/${alertSource}-icon.png`}
                        onError={handleImageError}
                      />
                    </svg>
                  ) : (
                    <QuestionMarkCircleIcon />
                  );
                return (
                  <Badge
                    icon={DynamicIcon}
                    key={t}
                    size="xs"
                    color="orange"
                    title={`Source: ${alertSource}`}
                  >
                    {t}
                  </Badge>
                );
              }
              return (
                <Badge key={t} size="xs" color="orange">
                  {t}
                </Badge>
              );
            })}
          </AccordionHeader>
          <AccordionBody>
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
          </AccordionBody>
        </Accordion>

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
              installedProvidersMode={selectedProvider.installed}
              isProviderNameDisabled={true}
            />
          )}
        </SlidingPanel>
      </Card>
    </div>
  );
}

export default WorkflowTile;
