interface Provider {
  type: string;
  config: string;
  with: { [key: string]: string | number | boolean | object };
}

interface Step {
  name: string;
  provider: Provider;
  if?: string;
}

interface Condition {
  name: string;
  type: string;
}

interface ThresholdCondition extends Condition {
  value: string;
  compare_to: string;
  level?: string;
}

interface AssertCondition extends Condition {
  assert: string;
}

export interface Action extends Step {
  condition?: ThresholdCondition | AssertCondition[];
  foreach?: string;
}

export interface LegacyWorkflow {
  id: string;
  disabled?: boolean;
  description?: string;
  owners?: string[];
  services?: string[];
  steps: Step[];
  actions?: Action[];
  triggers?: any;
  name?: string;
}
