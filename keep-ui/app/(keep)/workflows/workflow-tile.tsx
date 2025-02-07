"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import WorkflowMenu from "./workflow-menu";
import Loading from "@/app/(keep)/loading";
import { Trigger, Provider, Workflow } from "@/shared/api/workflows";
import { Button, Text, Card, Icon, ListItem, List, Badge } from "@tremor/react";
import ProviderForm from "@/app/(keep)/providers/provider-form";
import SlidingPanel from "react-sliding-side-panel";
import { useFetchProviders } from "@/app/(keep)/providers/page.client";
import { Provider as FullProvider } from "@/app/(keep)/providers/providers";
import {
  CheckCircleIcon,
  CursorArrowRaysIcon,
  XCircleIcon,
} from "@heroicons/react/24/outline";
import AlertTriggerModal from "./workflow-run-with-alert-modal";
import { formatDistanceToNowStrict } from "date-fns";
import TimeAgo, { Formatter, Suffix, Unit } from "react-timeago";
import WorkflowGraph from "./workflow-graph";
import { PiDiamondsFourFill } from "react-icons/pi";
import Modal from "@/components/ui/Modal";
import {
  MdOutlineKeyboardArrowRight,
  MdOutlineKeyboardArrowLeft,
} from "react-icons/md";
import { HiBellAlert } from "react-icons/hi2";
import { useWorkflowRun } from "utils/hooks/useWorkflowRun";
import { useWorkflowActions } from "@/entities/workflows/model/useWorkflowActions";
import "./workflow-tile.css";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useToggleWorkflow } from "utils/hooks/useWorkflowToggle";

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

export const ProvidersCarousel = ({
  providers,
  onConnectClick,
}: {
  providers: FullProvider[];
  onConnectClick: (provider: FullProvider) => void;
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);

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
              <DynamicImageProviderIcon
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
  const { toggleWorkflow, isToggling } = useToggleWorkflow(workflow.id);

  const { providers, mutate } = useFetchProviders();
  const { deleteWorkflow } = useWorkflowActions();
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
    deleteWorkflow(workflow.id);
  };

  const handleWorkflowClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    const target = e.target as HTMLElement;
    if (target.closest(".js-dont-propagate")) {
      // do not redirect if the three-dot menu is clicked
      return;
    }
    router.push(`/workflows/${workflow.id}`);
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
            return onlyIcons ? (
              <Badge
                key={t}
                size="xs"
                color="orange"
                title={`Source: ${alertSource}`}
                {...props}
              >
                <div className="flex justify-center items-center">
                  <DynamicImageProviderIcon
                    providerType={alertSource!}
                    width="16"
                    height="16"
                    color="orange"
                  />
                </div>
              </Badge>
            ) : (
              <Badge
                icon={() => (
                  <DynamicImageProviderIcon
                    providerType={alertSource!}
                    height="16"
                    width="16"
                  />
                )}
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
                  <Icon icon={CursorArrowRaysIcon} size="sm" color="orange" />
                </div>
              </Badge>
            ) : (
              <Badge
                key={t}
                size="xs"
                color="orange"
                icon={CursorArrowRaysIcon}
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
    <div>
      {isRunning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <Loading />
        </div>
      )}
      <Card
        className="relative flex flex-col justify-between bg-white rounded shadow p-2 h-full border-2 border-transparent hover:border-orange-400 overflow-hidden"
        onClick={handleWorkflowClick}
      >
        <div className="absolute top-0 right-0 mt-2 mr-2 mb-2 flex items-center flex-wrap">
          {workflow.provisioned && (
            <Badge color="orange" size="xs" className="mr-2 mb-2">
              Provisioned
            </Badge>
          )}
          {workflow.alertRule && (
            <Badge color="orange" size="xs" className="mr-2 mb-2">
              Alert Rule
            </Badge>
          )}
          {workflow.disabled && (
            <Badge color="slate" size="xs" className="mr-2 mb-2">
              Disabled
            </Badge>
          )}
          {!!handleRunClick && (
            <WorkflowMenu
              onDelete={handleDeleteClick}
              onRun={handleRunClick}
              onDownload={handleDownloadClick}
              onView={handleViewClick}
              onBuilder={handleBuilderClick}
              onToggleState={toggleWorkflow}
              isDisabled={workflow.disabled}
              runButtonToolTip={message}
              isRunButtonDisabled={!!isRunButtonDisabled}
              provisioned={workflow.provisioned}
            />
          )}
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
                  icon={CursorArrowRaysIcon}
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
                      <DynamicImageProviderIcon
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
                mutate={mutate}
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

export default WorkflowTile;
