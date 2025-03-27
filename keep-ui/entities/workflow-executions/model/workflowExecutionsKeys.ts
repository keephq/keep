export const workflowExecutionsKeys = {
  all: "workflow-executions",
  list: (
    workflowId: string,
    {
      limit,
      offset,
      searchParamsString,
    }: { limit: number; offset: number; searchParamsString: string }
  ) =>
    [
      workflowExecutionsKeys.all,
      "list",
      workflowId,
      limit,
      offset,
      searchParamsString,
    ].join("::"),
  detail: (workflowId: string, workflowExecutionId: string) =>
    [
      workflowExecutionsKeys.all,
      "detail",
      workflowId,
      workflowExecutionId,
    ].join("::"),
  getListMatcher: () => [workflowExecutionsKeys.all, "list"].join("::"),
  getDetailMatcher: (workflowId: string) =>
    [workflowExecutionsKeys.all, "detail", workflowId].join("::"),
};
