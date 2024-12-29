import { TrashIcon } from "@radix-ui/react-icons";
import { Button } from "@tremor/react";
import { MouseEvent } from "react";
import { useRules } from "utils/hooks/useRules";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";

type DeleteRuleCellProps = {
  ruleId: string;
};

export const DeleteRuleCell = ({ ruleId }: DeleteRuleCellProps) => {
  const api = useApi();
  const { mutate } = useRules();

  const onDeleteRule = async (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();

    const confirmed = confirm(`Are you sure you want to delete this rule?`);
    if (confirmed) {
      try {
        const response = await api.delete(`/rules/${ruleId}`);
        await mutate();
      } catch (error) {
        showErrorToast(error, "Failed to delete rule");
      }
    }
  };

  return (
    <Button
      className="invisible group-hover:visible"
      onClick={onDeleteRule}
      variant="secondary"
      color="red"
      size="xl"
    >
      <TrashIcon />
    </Button>
  );
};
