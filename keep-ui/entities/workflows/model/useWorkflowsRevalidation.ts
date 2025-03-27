// src/shared/lib/hooks/useWorkflowRevalidation.ts
import { useCallback } from "react";
import { workflowKeys } from "../lib/workflowKeys";
import { useSWRConfig } from "swr";

/**
 * Hook that provides functions to revalidate workflow-related cache entries
 */
export function useWorkflowRevalidation() {
  const { mutate } = useSWRConfig();
  /**
   * Revalidates all workflow list queries
   */
  const revalidateLists = useCallback(() => {
    return mutate(workflowKeys.getListMatcher());
  }, []);

  /**
   * Revalidates a specific workflow by ID
   */
  const revalidateDetail = useCallback((workflowId: string) => {
    return mutate(workflowKeys.detail(workflowId));
  }, []);

  /**
   * Revalidates both the lists and a specific workflow detail
   */
  const revalidateWorkflow = useCallback(
    (workflowId: string) => {
      revalidateLists();
      revalidateDetail(workflowId);
    },
    [revalidateLists, revalidateDetail]
  );

  return {
    revalidateLists,
    revalidateDetail,
    revalidateWorkflow,
  };
}
