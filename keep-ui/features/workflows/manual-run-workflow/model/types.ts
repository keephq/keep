export type AlertWorkflowRunPayload = {
  type: "alert";
  body: Record<string, any>;
  inputs?: Record<string, any>;
};

export type IncidentWorkflowRunPayload = {
  type: "incident";
  body: Record<string, any>;
  inputs?: Record<string, any>;
};

export type InputsWorkflowRunPayload = {
  type: undefined;
  inputs?: Record<string, any>;
};

export type WorkflowRunPayload =
  | AlertWorkflowRunPayload
  | IncidentWorkflowRunPayload
  | InputsWorkflowRunPayload;
