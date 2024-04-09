import QueryBuilder from "react-querybuilder";
import { RuleGroup } from "./RuleGroup";
import { Controller, useFormContext } from "react-hook-form";
import { CorrelationForm } from ".";

export const CreateCorrelationGroups = () => {
  const { control } = useFormContext<CorrelationForm>();

  return (
    <div>
      <p className="text-tremor-default font-medium text-tremor-content-strong mb-2">
        Add group(s) of conditions
      </p>
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
