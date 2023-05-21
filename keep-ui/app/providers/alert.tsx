import React from 'react';
import GrafanaAlert from './grafana-alert';
// Import other alert components for different providers

type AlertProps = {
  alert: any; // Replace 'any' with the type or interface representing the alert data structure
  provider: string; // Add a 'provider' prop to identify the provider of the alert
};

const Alert = ({ alert, provider }: AlertProps) => {
  // Render different alert components based on the provider
  switch (provider) {
    case 'grafana':
      return <GrafanaAlert alert={alert} />;
    // Add other cases for different providers and their respective alert components
    // case 'datadog':
    //   return <DatadogAlert alert={alert} />;
    // case 'other-provider':
    //   return <OtherProviderAlert alert={alert} />;
    default:
      return <div>Unknown provider: {provider}</div>;
  }
};

export default Alert;
