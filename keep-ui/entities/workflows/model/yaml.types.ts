interface YamlProvider {
  type: string;
  config: string;
  with: { [key: string]: string | number | boolean | object };
}

export interface YamlStepOrAction {
  name: string;
  provider: YamlProvider;
  id?: string;
  if?: string;
  vars?: Record<string, string>;
  condition?: (YamlThresholdCondition | YamlAssertCondition)[];
  foreach?: string;
}

interface YamlCondition {
  id?: string;
  name: string;
  alias?: string;
}

export interface YamlThresholdCondition extends YamlCondition {
  type: "threshold";
  value: string;
  compare_to: string;
  level?: string;
}

export interface YamlAssertCondition extends YamlCondition {
  type: "assert";
  assert: string;
}

export interface YamlWorkflowDefinition {
  id: string;
  disabled?: boolean;
  description?: string;
  owners?: string[];
  services?: string[];
  steps: YamlStepOrAction[];
  actions?: YamlStepOrAction[];
  triggers?: any;
  name?: string;
  consts?: Record<string, string>;
}
