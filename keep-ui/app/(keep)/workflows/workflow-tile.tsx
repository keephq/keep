"use client";

import { Workflow } from "./models";
import Image from "next/image";
import React, { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import WorkflowMenu from "./workflow-menu";
import Loading from "@/app/(keep)/loading";
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
import ProviderForm from "@/app/(keep)/providers/provider-form";
import SlidingPanel from "react-sliding-side-panel";
import { useFetchProviders } from "@/app/(keep)/providers/page.client";
import { Provider as FullProvider } from "@/app/(keep)/providers/providers";
import "./workflow-tile.css";
import { CheckCircleIcon, XCircleIcon } from "@heroicons/react/24/outline";
import AlertTriggerModal from "./workflow-run-with-alert-modal";
import { formatDistanceToNowStrict } from "date-fns";
import TimeAgo, { Formatter, Suffix, Unit } from "react-timeago";
import WorkflowGraph from "./workflow-graph";
import { PiDiamondsFourFill } from "react-icons/pi";
import Modal from "@/components/ui/Modal";
import { FaHandPointer } from "react-icons/fa";
import {
  MdOutlineKeyboardArrowRight,
  MdOutlineKeyboardArrowLeft,
} from "react-icons/md";
import { HiBellAlert } from "react-icons/hi2";
import { useWorkflowRun } from "utils/hooks/useWorkflowRun";
import { useApi } from "@/shared/lib/hooks/useApi";

function WorkflowMenuSection({
  onDelete,
  onRun,
  onDownload,
  onView,
  onBuilder,
  isRunButtonDisabled,
  runButtonToolTip,
  provisioned,
}: {
  onDelete: () => Promise<void>;
  onRun: () => Promise<void>;
  onDownload: () => void;
  onView: () => void;
  onBuilder: () => void;
  isRunButtonDisabled: boolean;
  runButtonToolTip?: string;
  provisioned?: boolean;
}) {
  // Determine if all providers are installed

  return (
    <WorkflowMenu
      onDelete={onDelete}
      onRun={onRun}
      onDownload={onDownload}
      onView={onView}
      onBuilder={onBuilder}
      isRunButtonDisabled={isRunButtonDisabled}
      runButtonToolTip={runButtonToolTip}
      provisioned={provisioned}
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

export const ProvidersCarousel = ({
  providers,
  onConnectClick,
}: {
  providers: FullProvider[];
  onConnectClick: (provider: FullProvider) => void;
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);

  const providersPerPage = 3;

  const nextIcons = () => {
    if (currentIndex + providersPerPage < providers.length) {
      setCurrentIndex(currentIndex + providersPerPage);
    }
  };

  const prevIcons = () => {
    if (currentIndex - providersPerPage >= 0) {
      setCurrentIndex(currentIndex - providersPerPage);
    }
  };

  const displayedProviders = providers.slice(
    currentIndex,
    currentIndex + providersPerPage
  );

  return (
    <div className="contianer flex flex-row justify-around items-center">
      <button
        className={`bg-transparent border-none text-2xl cursor-pointer ${
          currentIndex === 0 ? "opacity-50 cursor-not-allowed" : ""
        }`}
        onClick={prevIcons}
        disabled={currentIndex === 0}
      >
        <MdOutlineKeyboardArrowLeft size="2rem" />
      </button>
      <div className="container flex items-center justify-around overflow-hidden p-2">
        {displayedProviders.map((provider, index) => (
          <div
            key={index}
            className="relative p-2 hover:grayscale-0 text-2xl h-full shadow-md"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
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
            <Button
              onClick={() => onConnectClick(provider)}
              disabled={provider.installed}
              className="bg-transparent border-none hover:bg-transparent p-0"
            >
              <Image
                src={`/icons/${provider.type}-icon.png`}
                width={30}
                height={30}
                alt={provider.type}
                className={`${
                  provider.installed ? "" : "grayscale hover:grayscale-0"
                }`}
              />
            </Button>
          </div>
        ))}
      </div>
      <button
        className={`bg-transparent border-none text-2xl cursor-pointer ${
          currentIndex + providersPerPage >= providers.length
            ? "opacity-50 cursor-not-allowed"
            : ""
        }`}
        onClick={nextIcons}
        disabled={currentIndex + providersPerPage >= providers.length}
      >
        <MdOutlineKeyboardArrowRight size="2rem" />
      </button>
    </div>
  );
};

function WorkflowTile({ workflow }: { workflow: Workflow }) {
  const api = useApi();
  // Create a set to keep track of unique providers
  const router = useRouter();
  const [openPanel, setOpenPanel] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<FullProvider | null>(
    null
  );

  const [openTriggerModal, setOpenTriggerModal] = useState<boolean>(false);
  const alertSource = workflow?.triggers
    ?.find((w) => w.type === "alert")
    ?.filters?.find((f) => f.key === "source")?.value;
  const [fallBackIcon, setFallBackIcon] = useState(false);

  const { providers } = useFetchProviders();
  const {
    isRunning,
    handleRunClick,
    getTriggerModalProps,
    isRunButtonDisabled,
    message,
  } = useWorkflowRun(workflow!);

  const handleConnectProvider = (provider: FullProvider) => {
    setSelectedProvider(provider);
    // prepopulate it with the name
    setOpenPanel(true);
  };

  const handleCloseModal = () => {
    setOpenPanel(false);
    setSelectedProvider(null);
  };

  const handleDeleteClick = async () => {
    try {
      await api.delete(`/workflows/${workflow.id}`);
      // Workflow deleted successfully
      window.location.reload();
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

  const lastExecutions = workflow?.last_executions?.slice(0, 15) || [];
  const lastProviderConfigRequiredExec = lastExecutions.filter(
    (execution) => execution?.status === "providers_not_configured"
  );
  const isAllExecutionProvidersConfigured =
    lastProviderConfigRequiredExec.length === lastExecutions.length;

  const customFormatter: Formatter = (
    value: number,
    unit: Unit,
    suffix: Suffix
  ) => {
    if (!workflow.last_execution_started && isAllExecutionProvidersConfigured) {
      return "";
    }

    const formattedString = formatDistanceToNowStrict(
      new Date(workflow.last_execution_started + "Z"),
      { addSuffix: true }
    );

    return formattedString
      .replace("about ", "")
      .replace("minute", "min")
      .replace("second", "sec")
      .replace("hour", "hr");
  };

  const handleImageError = (event: any) => {
    event.target.href.baseVal = "/icons/keep-icon.png";
  };

  const isManualTriggerPresent = workflow?.triggers?.find(
    (t) => t.type === "manual"
  );

  const DynamicIconForTrigger = ({
    onlyIcons,
    interval,
    ...props
  }: {
    onlyIcons?: boolean;
    interval?: string;
    className?: string;
  }) => {
    return (
      <>
        {triggerTypes.map((t, index) => {
          if (t === "alert") {
            const DynamicIcon = (props: any) => (
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
            );
            return onlyIcons ? (
              <Badge
                key={t}
                size="xs"
                color="orange"
                title={`Source: ${alertSource}`}
                {...props}
              >
                <div className="flex justify-center items-center">
                  <DynamicIcon width="16px" height="16px" color="orange" />
                </div>
              </Badge>
            ) : (
              <Badge
                icon={DynamicIcon}
                key={t}
                size="xs"
                color="orange"
                title={`Source: ${alertSource}`}
                {...props}
              >
                {t}
              </Badge>
            );
          }
          if (t === "manual") {
            return onlyIcons ? (
              <Badge key={t} size="xs" color="orange" title={t} {...props}>
                <div className="flex justify-center items-center">
                  <FaHandPointer size={16} color="orange" />
                </div>
              </Badge>
            ) : (
              <Badge
                key={t}
                size="xs"
                color="orange"
                icon={FaHandPointer}
                title={`Source: ${t}`}
                {...props}
              >
                {t}
              </Badge>
            );
          }

          if (t === "interval" && onlyIcons) {
            return (
              <Badge
                key={t}
                size="xs"
                color="orange"
                title={`Source: ${t}`}
                {...props}
              >
                <div className="flex justify-center items-center">
                  <PiDiamondsFourFill size={16} color="orange" />
                  <div>{interval}</div>
                </div>
              </Badge>
            );
          }
          return !onlyIcons ? (
            <Badge key={t} color="orange">
              {t}
            </Badge>
          ) : null;
        })}
      </>
    );
  };

  return (
    <div className="mt-2.5">
      {isRunning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <Loading />
        </div>
      )}
      <Card
        className="relative flex flex-col justify-between bg-white rounded shadow p-2 h-full hover:border-orange-400 hover:border-2 overflow-hidden"
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          if (workflow.id) {
            router.push(`/workflows/${workflow.id}`);
          }
        }}
      >
        <div className="absolute top-0 right-0 mt-2 mr-2 mb-2 flex items-center flex-wrap">
          {workflow.provisioned && (
            <Badge color="orange" size="xs" className="mr-2 mb-2">
              Provisioned
            </Badge>
          )}
          {!!handleRunClick &&
            WorkflowMenuSection({
              onDelete: handleDeleteClick,
              onRun: handleRunClick,
              onDownload: handleDownloadClick,
              onView: handleViewClick,
              onBuilder: handleBuilderClick,
              runButtonToolTip: message,
              isRunButtonDisabled: !!isRunButtonDisabled,
              provisioned: workflow.provisioned,
            })}
        </div>
        <div className="m-2 flex flex-col justify-around item-start flex-wrap">
          <WorkflowGraph workflow={workflow} />
          <div className="container flex flex-col space-between">
            <div className="h-24 cursor-default">
              <h2 className="truncate leading-6 font-bold text-base md:text-lg lg:text-xl">
                {workflow?.name || "Unkown"}
              </h2>
              <p className="text-gray-500 line-clamp-2">
                {workflow?.description || "no description"}
              </p>
            </div>
            <div className="flex flex-row justify-between items-center gap-1 flex-wrap text-sm">
              {!!workflow?.interval && (
                <Button
                  className={`border bg-white border-gray-500 p-0.5 pr-1.5 pl-1.5 text-black placeholder-opacity-100 text-xs rounded-3xl hover:bg-gray-100 hover:border-gray font-bold shadow`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setOpenTriggerModal(true);
                  }}
                  icon={PiDiamondsFourFill}
                  tooltip={`time: ${workflow?.interval} secs`}
                >
                  Interval
                </Button>
              )}
              {isManualTriggerPresent && (
                <Button
                  className={`border bg-white border-gray-500 p-0.5 pr-1.5 pl-1.5 text-black placeholder-opacity-100 text-xs rounded-3xl hover:bg-gray-100 hover:border-gray font-bold shadow`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setOpenTriggerModal(true);
                  }}
                  icon={FaHandPointer}
                >
                  Manual
                </Button>
              )}
              {alertSource && (
                <Button
                  className={`border bg-white border-gray-500 p-0.5 pr-1.5 pl-1.5 text-black placeholder-opacity-100 text-xs rounded-3xl hover:bg-gray-100 hover:border-gray font-bold shadow`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setOpenTriggerModal(true);
                  }}
                  tooltip={`Source: ${alertSource}`}
                >
                  <div className="flex items-center justify-center gap-0.5">
                    {!fallBackIcon ? (
                      <Image
                        src={`/icons/${alertSource}-icon.png`}
                        width={20}
                        height={20}
                        alt={alertSource}
                        onError={() => setFallBackIcon(true)}
                        className="object-cover"
                      />
                    ) : (
                      <HiBellAlert size={20} />
                    )}
                    Trigger
                  </div>
                </Button>
              )}
              <div className="flex-1 text-gray-500 text-sm text-right cursor-pointer truncate max-w-full">
                {!isAllExecutionProvidersConfigured &&
                  workflow?.last_execution_started && (
                    <TimeAgo
                      date={workflow?.last_execution_started + "Z"}
                      formatter={customFormatter}
                    />
                  )}
              </div>
            </div>
          </div>
        </div>
        <div className="container p-2 hidden">
          <Card className="mt-2.5 p-2">
            <Text className="">Providers:</Text>
            <ProvidersCarousel
              providers={uniqueProviders}
              onConnectClick={handleConnectProvider}
            />
            {/* </div> */}
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
                onConnectChange={handleConnecting}
                closeModal={handleCloseModal}
                installedProvidersMode={selectedProvider.installed}
                isProviderNameDisabled={true}
              />
            )}
          </SlidingPanel>
        </div>
      </Card>

      {!!getTriggerModalProps && (
        <AlertTriggerModal {...getTriggerModalProps()} />
      )}
      <Modal
        isOpen={openTriggerModal}
        onClose={() => {
          setOpenTriggerModal(false);
        }}
      >
        <div className="mt-2.5">
          <div className="flex flex-row items-center justify-start flex-wrap gap-1">
            <span className="mr-1">Triggers:</span>
            <DynamicIconForTrigger />
          </div>
          <div>
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
          </div>
        </div>
      </Modal>
    </div>
  );
}

export function WorkflowTileOld({ workflow }: { workflow: Workflow }) {
  const api = useApi();
  // Create a set to keep track of unique providers
  const router = useRouter();
  const [openPanel, setOpenPanel] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<FullProvider | null>(
    null
  );

  const { providers } = useFetchProviders();
  const {
    isRunning,
    handleRunClick,
    isRunButtonDisabled,
    message,
    getTriggerModalProps,
  } = useWorkflowRun(workflow!);

  const handleConnectProvider = (provider: FullProvider) => {
    setSelectedProvider(provider);
    setOpenPanel(true);
  };

  const handleCloseModal = () => {
    setOpenPanel(false);
    setSelectedProvider(null);
  };

  const handleDeleteClick = async () => {
    try {
      await api.delete(`/workflows/${workflow.id}`);

      // Workflow deleted successfully
      window.location.reload();
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
    <div className="workflow-tile-basis mt-2.5">
      {isRunning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <Loading />
        </div>
      )}
      <Card>
        <div className="flex w-full justify-between items-center h-14">
          <Title className="truncate max-w-64 text-left text-lightBlack">
            {workflow.name}
          </Title>
          {!!handleRunClick &&
            WorkflowMenuSection({
              onDelete: handleDeleteClick,
              onRun: handleRunClick,
              onDownload: handleDownloadClick,
              onView: handleViewClick,
              onBuilder: handleBuilderClick,
              runButtonToolTip: message,
              isRunButtonDisabled: !!isRunButtonDisabled,
              provisioned: workflow.provisioned,
            })}
        </div>

        <div className="flex items-center justify-between h-10">
          <Text className="truncate max-w-sm text-left text-lightBlack">
            {workflow.description}
          </Text>
        </div>

        <List>
          <ListItem>
            <span>Created By</span>
            <span className="text-right">{workflow.created_by}</span>
          </ListItem>
          <ListItem>
            <span>Created At</span>
            <span className="text-right">
              {workflow.creation_time
                ? new Date(workflow.creation_time + "Z").toLocaleString()
                : "N/A"}
            </span>
          </ListItem>
          <ListItem>
            <span>Last Updated</span>
            <span className="text-right">
              {workflow.last_updated
                ? new Date(workflow.last_updated + "Z").toLocaleString()
                : "N/A"}
            </span>
          </ListItem>
          <ListItem>
            <span>Last Execution</span>
            <span className="text-right">
              {workflow.last_execution_time
                ? new Date(workflow.last_execution_time + "Z").toLocaleString()
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
          <ListItem>
            <span>Disabled</span>
            <span className="text-right">{workflow?.disabled?.toString()}</span>
          </ListItem>
        </List>

        <Accordion className="mt-2.5">
          <AccordionHeader>
            <span className="mr-1">Triggers:</span>
            {triggerTypes.map((t) => {
              if (t === "alert") {
                const handleImageError = (event: any) => {
                  event.target.href.baseVal = "/icons/keep-icon.png";
                };
                const alertSource = workflow.triggers
                  .find((w) => w.type === "alert")
                  ?.filters?.find((f) => f.key === "source")?.value;
                const DynamicIcon = (props: any) => (
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
              onConnectChange={handleConnecting}
              closeModal={handleCloseModal}
              installedProvidersMode={selectedProvider.installed}
              isProviderNameDisabled={true}
            />
          )}
        </SlidingPanel>
      </Card>
      {!!getTriggerModalProps && (
        <AlertTriggerModal {...getTriggerModalProps()} />
      )}
    </div>
  );
}

export default WorkflowTile;
