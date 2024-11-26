import { TrashIcon } from "@radix-ui/react-icons";
import { Button } from "@tremor/react";
import { MouseEvent } from "react";
import { useRules } from "utils/hooks/useRules";
import { useApi } from "@/shared/lib/hooks/useApi";
import { toast } from "react-toastify";
import { KeepApiError } from "@/shared/lib/api/KeepApiError";

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
        if (error instanceof KeepApiError) {
          toast.error(error.message || "Failed to delete rule");
        } else {
          toast.error(
            "Failed to delete rule, please contact us if this issue persists."
          );
        }
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
