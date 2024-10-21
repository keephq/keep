import { TrashIcon } from "@radix-ui/react-icons";
import { Button } from "@tremor/react";
import { useSession } from "next-auth/react";
import { MouseEvent } from "react";
import { useApiUrl } from "utils/hooks/useConfig";
import { useRules } from "utils/hooks/useRules";

type DeleteRuleCellProps = {
  ruleId: string;
};

export const DeleteRuleCell = ({ ruleId }: DeleteRuleCellProps) => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();
  const { mutate } = useRules();

  const onDeleteRule = async (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();

    if (session) {
      const confirmed = confirm(`Are you sure you want to delete this rule?`);
      if (confirmed) {
        const response = await fetch(`${apiUrl}/rules/${ruleId}`, {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${session.accessToken}`,
            "Content-Type": "application/json",
          },
        });

        if (response.ok) {
          await mutate();
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
