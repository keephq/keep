"use client";
import { Text } from "@tremor/react";
import { Providers, Provider } from "./providers";
import { useState } from "react";
import SlidingPanel from "react-sliding-side-panel";
import ProviderForm from "./provider-form";
import ProviderTile from "./provider-tile";
import "./providers-available.css";
import "react-sliding-side-panel/lib/index.css";

const ProvidersConnect = ({
  providers,
  addProvider,
}: {
  providers: Providers;
  addProvider: (provider: Provider) => void;
}) => {
  const [openPanel, setOpenPanel] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null
  );
  const [formValues, setFormValues] = useState<{ [key: string]: string }>({});
  const [formErrors, setFormErrors] = useState<{ [key: string]: string }>({});

  const handleFormChange = (
    updatedFormValues: Record<string, string>,
    updatedFormErrors: Record<string, string>
  ) => {
    setFormValues(updatedFormValues);
    setFormErrors(updatedFormErrors);
  };

  const handleConnectProvider = (provider: Provider) => {
    setSelectedProvider(provider);
    setOpenPanel(true);
  };

  const handleCloseModal = () => {
    setOpenPanel(false);
    setSelectedProvider(null);
    setFormValues({});
    setFormErrors({});
  };

  const handleConnecting = (isConnecting: boolean, isConnected: boolean) => {
    if (isConnected) handleCloseModal();
  };

  const providersWithConfig = providers
    .filter((provider) => {
      const config = (provider as Provider).config;
      return config && Object.keys(config).length > 0; // Filter out providers with empty config
    })
    .sort(
      (a, b) => Number(b.can_setup_webhook) - Number(a.can_setup_webhook)
    ) as Providers;

  return (
    <div>
      <Text className="ml-2.5 mt-5">Available Providers</Text>
      <div className="provider-tiles">
        {providersWithConfig.map((provider, index) => (
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
            onAddProvider={addProvider}
            closeModal={handleCloseModal}
          />
        )}
      </SlidingPanel>
    </div>
  );
};

export default ProvidersConnect;
