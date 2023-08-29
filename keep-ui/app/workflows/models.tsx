export type Provider = {
  id: string;
  type: string; // This corresponds to the name of the icon, e.g., "slack", "github", etc.
  name: string;
  installed: boolean;
}

type Filter = {
  key: string;
  value: string;
};

export type Trigger = {
  type: string;
  filters?: Filter[];
  value?: string;
};


export type Workflow = {
  id: string;
  description: string;
  created_by: string;
  creation_time: string;
  interval: string; // This can be a string like "Everyday at 9AM" or whatever suits you.
  providers: Provider[];
  triggers: Trigger[];
  last_execution_time: string;
  last_execution_status: string;
}
