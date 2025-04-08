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
  detail: (workflowId: string | null, workflowExecutionId: string) =>
    [
      workflowExecutionsKeys.all,
      "detail",
      workflowId,
      workflowExecutionId,
    ].join("::"),
  getListMatcher: () => (key: any) =>
    key.startsWith([workflowExecutionsKeys.all, "list"].join("::")),
  getDetailMatcher: (workflowId: string) => (key: any) =>
    key.startsWith(
      [workflowExecutionsKeys.all, "detail", workflowId].join("::")
    ),
};
