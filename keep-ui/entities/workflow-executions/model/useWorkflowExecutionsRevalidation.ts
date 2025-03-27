import { useSWRConfig } from "swr";
import { workflowExecutionsKeys } from "./workflowExecutionsKeys";

export const useWorkflowExecutionsRevalidation = () => {
  const { mutate } = useSWRConfig();

  const revalidateLists = () => {
    mutate(workflowExecutionsKeys.getListMatcher());
  };

  const revalidateForWorkflow = (workflowId: string) => {
    mutate(workflowExecutionsKeys.getDetailMatcher(workflowId));
    revalidateLists();
  };

  return {
    revalidateLists,
    revalidateForWorkflow,
  };
};
