type Provider = {
  id: string;
  type: string; // This corresponds to the name of the icon, e.g., "slack", "github", etc.
  name: string;
  installed: boolean;
}

export type Workflow = {
  id: string;
  description: string;
  created_by: string;
  creation_time: string;
  interval: string; // This can be a string like "Everyday at 9AM" or whatever suits you.
  providers: Provider[];
}
