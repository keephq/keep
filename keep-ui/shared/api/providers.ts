export interface ProviderAuthConfig {
  description: string;
  hint?: string;
  placeholder?: string;
  validation?:
    | "any_url"
    | "any_http_url"
    | "https_url"
    | "no_scheme_url"
    | "multihost_url"
    | "no_scheme_multihost_url"
    | "port"
    | "tld";
  required?: boolean;
  value?: string;
  default: string | number | boolean | null;
  options?: Array<string | number>;
  sensitive?: boolean;
  hidden?: boolean;
  type?: "select" | "form" | "file" | "switch";
  file_type?: string;
  config_main_group?: string;
  config_sub_group?: string;
}

export interface ProviderMethodParam {
  name: string;
  type: string;
  mandatory: boolean;
  default?: string;
  expected_values?: string[];
  autocomplete?: boolean;
}

export interface ProviderMethod {
  name: string;
  scopes: string[];
  func_name: string;
  description: string;
  category: string;
  generic_action?: boolean;
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
  | "AI"
  | "Monitoring"
  | "Incident Management"
  | "Cloud Infrastructure"
  | "Ticketing"
  | "Developer Tools"
  | "Database"
  | "Identity and Access Management"
  | "Security"
  | "Collaboration"
  | "CRM"
  | "Queues"
  | "Coming Soon"
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
  pulling_available: boolean;
  pulling_enabled: boolean;
  alertsDistribution?: AlertDistritbuionData[];
  alertExample?: { [key: string]: string };
  provisioned?: boolean;
  categories: TProviderCategory[];
  coming_soon: boolean;
  health: boolean;
  oauth2_installation?: boolean;
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
  pulling_available: false,
  pulling_enabled: true,
  categories: ["Others"],
  coming_soon: false,
  health: false,
};

export type ProviderFormKVData = Record<string, string>[];
export type ProviderFormValue =
  | string
  | number
  | boolean
  | File
  | ProviderFormKVData
  | undefined;
export type ProviderFormData = Record<string, ProviderFormValue>;
export type ProviderInputErrors = Record<string, string>;
