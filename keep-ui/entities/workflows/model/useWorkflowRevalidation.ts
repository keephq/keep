// src/shared/lib/hooks/useWorkflowRevalidation.ts
import { useCallback } from "react";
import { workflowKeys } from "./workflowKeys";
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
  const revalidateDetail = useCallback(
    (workflowId: string, workflowRevision: number | null = null) => {
      return mutate(workflowKeys.detail(workflowId, workflowRevision));
    },
    []
  );

  const revalidateWorkflowRevisions = useCallback((workflowId: string) => {
    return mutate(workflowKeys.revisions(workflowId));
  }, []);

  /**
   * Revalidates both the lists and a specific workflow detail
   */
  const revalidateWorkflow = useCallback(
    (workflowId: string, workflowRevision: number | null = null) => {
      revalidateLists();
      revalidateWorkflowRevisions(workflowId);
      revalidateDetail(workflowId, workflowRevision);
    },
    [revalidateLists, revalidateDetail, revalidateWorkflowRevisions]
  );

  return {
    revalidateLists,
    revalidateDetail,
    revalidateWorkflow,
    revalidateWorkflowRevisions,
  };
}
