"use client";
import { Icon, Title } from "@tremor/react";
import { Providers, Provider } from "./providers";
import { useEffect, useState } from "react";
// TODO: replace with custom component, package is not updated for last 4 years
import SlidingPanel from "react-sliding-side-panel";
import ProviderForm from "./provider-form";
import ProviderTile from "./provider-tile";
import "react-sliding-side-panel/lib/index.css";
import { useSearchParams } from "next/navigation";
import { QuestionMarkCircleIcon } from "@heroicons/react/24/outline";

const ProvidersTiles = ({
  providers,
  installedProvidersMode = false,
  linkedProvidersMode = false,
  isLocalhost = false,
}: {
  providers: Providers;
  installedProvidersMode?: boolean;
  linkedProvidersMode?: boolean;
  isLocalhost?: boolean;
}) => {
  const searchParams = useSearchParams();
  const [openPanel, setOpenPanel] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null
  );

  const providerType = searchParams?.get("provider_type");
  const providerName = searchParams?.get("provider_name");

  useEffect(() => {
    if (providerType) {
      // Find the provider based on providerType and providerName
      const provider = providers.find(
        (provider) => provider.type === providerType
      );

      if (provider) {
        setSelectedProvider(provider);
        setOpenPanel(true);
      }
    }
  }, [providerType, providerName, providers]);

  const handleConnectProvider = (provider: Provider) => {
    // on linked providers, don't open the modal
    if (provider.linked) return;
    setSelectedProvider(provider);
    setOpenPanel(true);
  };

  const handleCloseModal = () => {
    setOpenPanel(false);
    setSelectedProvider(null);
  };

  const handleConnecting = (isConnecting: boolean, isConnected: boolean) => {
    if (isConnected) handleCloseModal();
  };

  const getSectionTitle = () => {
    if (installedProvidersMode) {
      return "Installed Providers";
    }

    if (linkedProvidersMode) {
      return "Linked Providers";
    }

    return "Connect Provider";
  };

  const sortedProviders = providers
    .filter(
      (provider) =>
        Object.keys(provider.config || {}).length > 0 ||
        (provider.tags && provider.tags.includes("alert"))
    )
    .sort(
      (a, b) =>
        Number(b.can_setup_webhook) - Number(a.can_setup_webhook) ||
        Number(b.supports_webhook) - Number(a.supports_webhook) ||
        Number(b.oauth2_url ? true : false) -
          Number(a.oauth2_url ? true : false)
    );

  return (
    <div>
      <div className="flex items-center mb-2.5">
        <Title>{getSectionTitle()}</Title>
        {linkedProvidersMode && (
          <div className="relative">
            <Icon
              icon={QuestionMarkCircleIcon} // Use the appropriate icon for your use case
              className="text-gray-400 hover:text-gray-600"
              size="sm"
              tooltip="Providers which send alerts without being installed by Keep"
            />
          </div>
        )}
      </div>

      <div className="flex flex-wrap mb-5 gap-5">
        {sortedProviders.map((provider) => (
          <ProviderTile
            key={provider.id}
            provider={provider}
            onClick={() => handleConnectProvider(provider)}
          ></ProviderTile>
        ))}
      </div>

      <SlidingPanel
        type={"right"}
        isOpen={openPanel}
        size={
          window.innerWidth < 640 ? 100 : window.innerWidth < 1024 ? 80 : 40
        }
        backdropClicked={handleCloseModal}
        panelContainerClassName="bg-white z-[100]"
      >
        {selectedProvider && (
          <ProviderForm
            provider={selectedProvider}
            onConnectChange={handleConnecting}
            closeModal={handleCloseModal}
            installedProvidersMode={installedProvidersMode}
            isProviderNameDisabled={installedProvidersMode}
            isLocalhost={isLocalhost}
          />
        )}
      </SlidingPanel>
    </div>
  );
};

export default ProvidersTiles;
