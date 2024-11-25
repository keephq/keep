import QueryBuilder from "react-querybuilder";
import { RuleGroup } from "./RuleGroup";
import { Controller, useFormContext } from "react-hook-form";
import { CorrelationForm } from ".";
import { Button } from "@tremor/react";
import { QuestionMarkCircleIcon } from "@heroicons/react/24/outline";

export const CorrelationGroups = () => {
  const { control } = useFormContext<CorrelationForm>();

  return (
    <div className="col-span-2">
      <div className="flex justify-between items-center">
        <p className="text-tremor-default font-medium text-tremor-content-strong mb-2">
          Add filters
        </p>

        <Button
          className="cursor-default"
          type="button"
          tooltip="A Rule contains one or more Correlations, each evaluating a separate alert group. Results are combined using an AND operator. For instance, to group alerts by severity 'critical' and source 'Kibana', create two alert groups: one with severity = 'critical' and another with source = 'Kibana'."
          icon={QuestionMarkCircleIcon}
          size="xs"
          variant="light"
          color="slate"
        />
      </div>
      <Controller
        control={control}
        name="query"
        render={({ field: { value, onChange } }) => (
          <QueryBuilder
            query={value}
            onQueryChange={onChange}
            addRuleToNewGroups
            controlElements={{
              ruleGroup: RuleGroup,
            }}
          />
        )}
      />
    </div>
  );
};
