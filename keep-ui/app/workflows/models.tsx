type Provider = {
  provider_id: string;
  provider_type: string; // This corresponds to the name of the icon, e.g., "slack", "github", etc.
}

type Step = {
  name: string;
  description: string;
  provider: Provider;
}

type Action = {
  name: string;
  description: string;
  provider: Provider;
}

export type Workflow = {
  workflow_id: string;
  description: string;
  owners: string[];
  interval: string; // This can be a string like "Everyday at 9AM" or whatever suits you.
  steps: Step[];
  actions: Action[];
}
