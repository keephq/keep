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
  type?: string;
  file_type?: string;
}

export interface ProviderMethodParam {
  name: string;
  type: string;
  mandatory: boolean;
  default?: string;
  expected_values?: string[];
}

export interface ProviderMethod {
  name: string;
  scopes: string[];
  func_name: string;
  description: string;
  category: string;
  type: "view" | "action";
  func_params?: ProviderMethodParam[];
}

export interface ProviderScope {
  name: string;
  description?: string;
  mandatory: boolean;
  documentation_url?: string;
  alias?: string;
  mandatory_for_webhook: boolean;
}

export interface ProvidersResponse {
  providers: Provider[];
  installed_providers: Provider[];
  linked_providers: Provider[];
  is_localhost: boolean;
}

interface AlertDistritbuionData {
  hour: string;
  number: number;
}

export type TProviderCategory =
  | "Monitoring"
  | "Incident Management"
  | "Cloud Infrastructure"
  | "Ticketing"
  | "Identity"
  | "Developer Tools"
  | "Database"
  | "Identity and Access Management"
  | "Security"
  | "Collaboration"
  | "CRM"
  | "Queues"
  | "Others";

export type TProviderLabels =
  | "alert"
  | "incident"
  | "topology"
  | "messaging"
  | "ticketing"
  | "data"
  | "queue";

export interface Provider {
  // key value pair of auth method name and auth method config
  config: {
    [configKey: string]: ProviderAuthConfig;
  };
  // whether the provider is installed or not
  installed: boolean;
  linked: boolean;
  last_alert_received: string;
  // if the provider is installed, this will be the auth details
  //  otherwise, this will be null
  details: {
    authentication: {
      [authKey: string]: string;
    };
    name?: string;
  };
  // the id of the provider
  id: string;
  // the name of the provider
  display_name: string;
  comingSoon?: boolean;
  can_query: boolean;
  query_params?: string[];
  can_notify: boolean;
  notify_params?: string[];
  type: string;
  can_setup_webhook?: boolean;
  webhook_required?: boolean;
  supports_webhook?: boolean;
  provider_description?: string;
  oauth2_url?: string;
  scopes?: ProviderScope[];
  validatedScopes: { [scopeName: string]: boolean | string };
  methods?: ProviderMethod[];
  tags: TProviderLabels[];
  last_pull_time?: Date;
  pulling_enabled: boolean;
  alertsDistribution?: AlertDistritbuionData[];
  alertExample?: { [key: string]: string };
  provisioned?: boolean;
  categories: TProviderCategory[];
  coming_soon: boolean;
}

export type Providers = Provider[];

export const defaultProvider: Provider = {
  config: {}, // Set default config as an empty object
  installed: false, // Set default installed value
  linked: false, // Set default linked value
  last_alert_received: "", // Set default last alert received value
  details: { authentication: {}, name: "" }, // Set default authentication details as an empty object
  id: "", // Placeholder for the provider ID
  display_name: "", // Placeholder for the provider name
  can_notify: false,
  can_query: false,
  type: "",
  tags: [],
  validatedScopes: {},
  pulling_enabled: true,
  categories: ["Others"],
  coming_soon: false,
};
