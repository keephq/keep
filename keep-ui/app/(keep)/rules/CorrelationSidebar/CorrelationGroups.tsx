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
          tooltip="Any Rule consists of one or more Correlations. Each alert group is evaluated separately and the results are combined using AND combinator.
                  For example, if you want to group alerts that has a severity of 'critical' and another alert with a source of 'Kibana', you would create a rule with two alert groups.
                  The first alert group would have a rule with severity = 'critical' and the second alert group would have a rule with source = 'kibana'."
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
