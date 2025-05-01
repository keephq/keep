import { Fragment, useMemo } from "react";
import { Dialog, Transition } from "@headlessui/react";
import { CorrelationSidebarHeader } from "./CorrelationSidebarHeader";
import { CorrelationSidebarBody } from "./CorrelationSidebarBody";
import { CorrelationFormType } from "./types";
import { Drawer } from "@/shared/ui/Drawer";
import { Rule } from "@/utils/hooks/useRules";
import { DefaultRuleGroupType, parseCEL } from "react-querybuilder";

const TIMEFRAME_UNITS_FROM_SECONDS = {
  seconds: (amount: number) => amount,
  minutes: (amount: number) => amount / 60,
  hours: (amount: number) => amount / 3600,
  days: (amount: number) => amount / 86400,
} as const;

export const DEFAULT_CORRELATION_FORM_VALUES: CorrelationFormType = {
  name: "",
  description: "",
  timeAmount: 24,
  timeUnit: "hours",
  groupedAttributes: [],
  requireApprove: false,
  resolveOn: "never",
  createOn: "any",
  incidentNameTemplate: "",
  incidentPrefix: "",
  multiLevel: false,
  multiLevelPropertyName: "",
  query: {
    combinator: "or",
    rules: [
      {
        combinator: "and",
        rules: [{ field: "source", operator: "=", value: "" }],
      },
      {
        combinator: "and",
        rules: [{ field: "source", operator: "=", value: "" }],
      },
    ],
  },
};

type CorrelationSidebarProps = {
  isOpen: boolean;
  toggle: VoidFunction;
  selectedRule?: Rule;
  defaultValue?: CorrelationFormType;
};

export const CorrelationSidebar = ({
  isOpen,
  toggle,
  selectedRule,
}: CorrelationSidebarProps) => {
  const correlationFormFromRule: CorrelationFormType = useMemo(() => {
    if (selectedRule) {
      const query = parseCEL(selectedRule.definition_cel);
      const anyCombinator = query.rules.some((rule) => "combinator" in rule);

      const queryInGroup: DefaultRuleGroupType = {
        ...query,
        rules: anyCombinator
          ? query.rules
          : [
              {
                combinator: "and",
                rules: query.rules,
              },
            ],
      };

      const timeunit = selectedRule.timeunit ?? "seconds";

      return {
        name: selectedRule.name,
        description: selectedRule.group_description ?? "",
        timeAmount: TIMEFRAME_UNITS_FROM_SECONDS[timeunit](
          selectedRule.timeframe
        ),
        timeUnit: timeunit,
        groupedAttributes: selectedRule.grouping_criteria,
        requireApprove: selectedRule.require_approve,
        resolveOn: selectedRule.resolve_on,
        createOn: selectedRule.create_on,
        query: queryInGroup,
        incidents: selectedRule.incidents,
        incidentNameTemplate: selectedRule.incident_name_template || "",
        incidentPrefix: selectedRule.incident_prefix || "",
        multiLevel: selectedRule.multi_level,
        multiLevelPropertyName: selectedRule.multi_level_property_name || "",
      };
    }

    return DEFAULT_CORRELATION_FORM_VALUES;
  }, [selectedRule]);

  return (
    <Drawer
      isOpen={isOpen}
      onClose={toggle}
      className="fixed right-0 inset-y-0 min-w-12 bg-white p-6 overflow-auto flex flex-col"
    >
      <div className="flex flex-col h-full max-h-full overflow-hidden">
        <CorrelationSidebarHeader toggle={toggle} />
        <CorrelationSidebarBody
          toggle={toggle}
          defaultValue={correlationFormFromRule}
        />
      </div>
    </Drawer>
  );
};
