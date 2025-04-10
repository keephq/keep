import { WorkflowsQuery } from "./useWorkflowsV2";

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
      .filter((p) => p !== undefined && p !== null)
      .join("::"),
  detail: (id: string) => [workflowKeys.all, "detail", id].join("::"),
  getListMatcher: () => (key: any) =>
    typeof key === "string" &&
    key.startsWith([workflowKeys.all, "list"].join("::")),
};
