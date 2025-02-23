interface YamlProvider {
  type: string;
  config: string;
  with: { [key: string]: string | number | boolean | object };
}

export interface YamlStep {
  name: string;
  provider: YamlProvider;
  if?: string;
  vars?: Record<string, string>;
}

interface YamlCondition {
  name: string;
  type: string;
}

interface YamlThresholdCondition extends YamlCondition {
  value: string;
  compare_to: string;
  level?: string;
}

interface YamlAssertCondition extends YamlCondition {
  assert: string;
}

export interface YamlAction extends YamlStep {
  condition?: YamlThresholdCondition | YamlAssertCondition[];
  foreach?: string;
}

export interface YamlWorkflowDefinition {
  id: string;
  disabled?: boolean;
  description?: string;
  owners?: string[];
  services?: string[];
  steps: YamlStep[];
  actions?: YamlAction[];
  triggers?: any;
  name?: string;
  consts?: Record<string, string>;
}
