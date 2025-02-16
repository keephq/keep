import { Icon } from "@tremor/react";
import ProviderForm from "../../providers/provider-form";
import { Provider as FullProvider } from "@/app/(keep)/providers/providers";
import { useState } from "react";
import { Workflow, Provider } from "@/shared/api/workflows";
import { CheckCircleIcon, XCircleIcon } from "@heroicons/react/24/outline";
import { DynamicImageProviderIcon } from "@/components/ui";
import SlidingPanel from "react-sliding-side-panel";
import { useFetchProviders } from "../../providers/page.client";

export const ProvidersCarousel = ({
  providers,
  onConnectClick,
}: {
  providers: FullProvider[];
  onConnectClick: (provider: FullProvider) => void;
}) => {
  return (
    <div className="flex flex-wrap gap-2">
      {providers.map((provider, index) => (
        <div
          key={index}
          className="relative border border-gray-200 rounded-md p-2"
        >
          <button
            onClick={() => onConnectClick(provider)}
            disabled={provider.installed}
            className="flex items-center gap-2"
          >
            <DynamicImageProviderIcon
              src={`/icons/${provider.type}-icon.png`}
              width={30}
              height={30}
              alt={provider.type}
            />
            <span className="text-sm">{provider.display_name}</span>
            {provider.installed ? (
              <Icon
                icon={CheckCircleIcon}
                color="green"
                size="sm"
                tooltip="Connected"
              />
            ) : (
              <Icon
                icon={XCircleIcon}
                color="red"
                size="sm"
                tooltip="Disconnected"
              />
            )}
          </button>
        </div>
      ))}
    </div>
  );
};

export function WorkflowProviders({ workflow }: { workflow: Workflow }) {
  const [openPanel, setOpenPanel] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<FullProvider | null>(
    null
  );
  const { providers, mutate } = useFetchProviders();

  const handleConnectProvider = (provider: FullProvider) => {
    setSelectedProvider(provider);
    // prepopulate it with the name
    setOpenPanel(true);
  };

  const handleCloseModal = () => {
    setOpenPanel(false);
    setSelectedProvider(null);
  };

  const handleConnecting = (isConnecting: boolean, isConnected: boolean) => {
    if (isConnected) {
      handleCloseModal();
      // refresh the page to show the changes
      window.location.reload();
    }
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

  return (
    <>
      <ProvidersCarousel
        providers={uniqueProviders}
        onConnectClick={handleConnectProvider}
      />
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
    </>
  );
}
