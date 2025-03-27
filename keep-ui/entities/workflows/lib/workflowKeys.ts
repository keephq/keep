import { WorkflowsQuery } from "../model/useWorkflowsV2";

export const workflowKeys = {
  all: "workflows",
  list: (query: WorkflowsQuery) =>
    [
      workflowKeys.all,
      "list",
      query.cel,
      query.limit,
      query.offset,
      query.sortBy,
      query.sortDir,
    ]
      .filter(Boolean)
      .join("::"),
  detail: (id: string) => [workflowKeys.all, "detail", id].join("::"),
  getListMatcher: () => (key: any) =>
    key.startsWith([workflowKeys.all, "list"].join("::")),
};
