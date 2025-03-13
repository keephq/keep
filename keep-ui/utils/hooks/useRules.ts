import useSWR, { SWRConfiguration } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";

export type Rule = {
  id: string;
  name: string;
  item_description: string | null;
  group_description: string | null;
  grouping_criteria: string[];
  definition_cel: string;
  definition: { sql: string; params: {} };
  timeframe: number;
  timeunit: "minutes" | "seconds" | "hours" | "days";
  created_by: string;
  creation_time: string;
  tenant_id: string;
  updated_by: string | null;
  update_time: string | null;
  require_approve: boolean;
  resolve_on: "all" | "first" | "last" | "never";
  create_on: "any" | "all";
  distribution: { [group: string]: { [timestamp: string]: number } };
  incidents: number;
  incident_name_template: string | null;
  incident_prefix: string | null;
};

export const useRules = (options?: SWRConfiguration) => {
  const api = useApi();

  return useSWR<Rule[]>(
    api.isReady() ? "/rules" : null,
    (url) => api.get(url),
    options
  );
};
