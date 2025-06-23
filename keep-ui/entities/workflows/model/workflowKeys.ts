import { WorkflowsQuery, WorkflowTemplatesQuery } from "./useWorkflowsV2";

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
  templates: (query: WorkflowTemplatesQuery) =>
    [workflowKeys.all, "templates", query.cel, query.limit, query.offset]
      .filter((p) => p !== undefined && p !== null)
      .join("::"),
  detail: (id: string, revision: number | null) =>
    [workflowKeys.all, "detail", id, revision].join("::"),
  revisions: (workflowId: string) =>
    [workflowKeys.all, "revisions", workflowId].join("::"),
  getListMatcher: () => (key: any) =>
    typeof key === "string" &&
    key.startsWith([workflowKeys.all, "list"].join("::")),
};
