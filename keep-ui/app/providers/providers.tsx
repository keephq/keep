export interface ProviderAuthConfig {
  name: string;
  description: string;
  hint?: string;
  placeholder?: string;
  validation: string; // regex
  required?: boolean;
  value?: string;
  sensitive?: boolean;
  hidden?: boolean;
}

export interface Provider {
  // key value pair of auth method name and auth method config
  config: {
    [configKey: string]: ProviderAuthConfig;
  };
  // whether the provider is installed or not
  installed: boolean;
  // if the provider is installed, this will be the auth details
  //  otherwise, this will be null
  details: {
    authentication: {
      [authKey: string]: string;
    };
    name?: string;
  };
  // the name of the provider
  id: string;
  // the name of the provider
  comingSoon?: boolean;
  can_query: boolean;
  query_params?: string[];
  can_notify: boolean;
  notify_params?: string[];
  type: string;
  can_setup_webhook?: boolean;
  supports_webhook?: boolean;
  provider_description?: string;
  oauth2_url?: string;
}

export type Providers = Provider[];

export const defaultProvider: Provider = {
  config: {}, // Set default config as an empty object
  installed: false, // Set default installed value
  details: { authentication: {}, name: "" }, // Set default authentication details as an empty object
  id: "", // Placeholder for the provider ID
  can_notify: false,
  can_query: false,
  type: "",
};
