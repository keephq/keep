import { RuleGroupType } from "react-querybuilder";

export type CorrelationFormType = {
  name: string;
  description: string;
  timeAmount: number;
  timeUnit: "minutes" | "seconds" | "hours" | "days";
  groupedAttributes: string[];
  requireApprove: boolean;
  resolveOn: "all" | "first" | "last" | "never";
  createOn: "any" | "all";
  query: RuleGroupType;
  incidentNameTemplate: string;
  incidentPrefix: string;
};
