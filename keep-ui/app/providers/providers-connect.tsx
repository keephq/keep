'use client';
import { Card } from "@tremor/react";
import ReactLoading from 'react-loading';
import { Providers, Provider } from "./providers";
import { useState } from "react";
import Modal from "react-modal";
import Image from "next/image";
import ProviderForm from "./provider-form"; // Import the ProviderForm component
import "./providers-connect.css"

const ProvidersConnect = ({
  providers,
  addProvider,
}: {
  providers: Providers;
  addProvider: (provider: Provider) => void;
}) => {
  const [showProviderModal, setShowProviderModal] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null
  );
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [formValues, setFormValues] = useState<{ [key: string]: string }>({});
  const [formErrors, setFormErrors] = useState<{ [key: string]: string }>({});

  const handleFormChange = (updatedFormValues: Record<string, string>, updatedFormErrors: Record<string, string>) => {
    setFormValues(updatedFormValues);
    setFormErrors(updatedFormErrors);
  };

  const handleConnectProvider = (provider: Provider) => {
    setSelectedProvider(provider);
    setShowProviderModal(true);
  };

  const handleCloseModal = () => {
    setShowProviderModal(false);
    setSelectedProvider(null);
    setIsConnecting(false);
    setIsConnected(false);
    setFormValues({});
    setFormErrors({});
  };

  const handleConnecting = (isConnecting: boolean, isConnected: boolean) => {
    setIsConnecting(isConnecting);
    setIsConnected(isConnected);
  }

  const providersWithConfig = providers.filter((provider) => {
      const config = (provider as Provider).config;
      return config && Object.keys(config).length > 0; // Filter out providers with empty config
    }) as Providers;


  return (
    <div>
      <div className="provider-tiles">
        {Object.values(providersWithConfig).map((provider, index) => (
          <Card
            key={provider.id}
            onClick={() => handleConnectProvider(provider)}
            className="card"
            style={{ gridColumn: "span 1" }}
          >
            <div className="image-wrapper">
              <Image
                src={`${provider.id}.svg`}
                alt={provider.id}
                width={150}
                height={150}
                onError={(event) => {
                  const target = event.target as HTMLImageElement;
                  target.src = "keep.svg"; // Set fallback icon
                }}
              />
            </div>
          </Card>
        ))}
      </div>
      <Modal
        isOpen={showProviderModal}
        onRequestClose={handleCloseModal}
        contentLabel="Connect Provider Modal"
        className="provider-modal"
      >
      {isConnecting || isConnected ? (
            <div className="loading-container">
              {isConnecting ? (
                <ReactLoading type="spin" color="rgb(234 160 112)" height={50} width={50} />
              ) : (
                <div className="complete-animation">Complete</div>
              )}
          </div>
        ) : (
    <>
      {selectedProvider && (
      <ProviderForm
        provider={selectedProvider}
        formData={formValues}
        formErrorsData={formErrors}
        onFormChange={handleFormChange}
        onConnectChange={handleConnecting}
        onAddProvider={addProvider}
      />
    )}

    </>
  )}
</Modal>

    </div>
  );
};

export default ProvidersConnect;
