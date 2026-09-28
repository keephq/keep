import { parseWorkflowYamlToJSON } from "@/entities/workflows/lib/yaml-utils";
import { fromZodError } from "zod-validation-error";

/**
 * Regression for #6274.
 *
 * The YAML import path in `workflow-builder-widget.tsx` used to call
 * `parseWorkflowYamlStringToJSON`, a bare `yaml.parse()` with no schema
 * validation. A `with:` written as a sibling of `provider:` (rather than nested
 * inside it) was therefore accepted, but every consumer reads
 * `provider.with` — so the parameters were silently dropped and the workflow
 * saved and fired with none of them.
 *
 * These tests pin the validation the import handler now performs.
 */

// Mirrors the import handler in workflow-builder-widget.tsx
const validateImportedWorkflow = (contents: string): string | null => {
  const result = parseWorkflowYamlToJSON(contents);
  if (!result.success) {
    return fromZodError(result.error).toString();
  }
  return null;
};

const MISPLACED_WITH = `workflow:
  id: test-with-nesting
  name: Test
  description: Regression fixture for issue 6274
  triggers:
    - type: alert
      filters:
        - key: source
          value: prometheus
  actions:
    - name: test-ntfy
      provider:
        type: ntfy
        config: default
      with:
        message: "test"`;

const NESTED_WITH = `workflow:
  id: test-with-nesting
  name: Test
  description: Regression fixture for issue 6274
  triggers:
    - type: alert
      filters:
        - key: source
          value: prometheus
  actions:
    - name: test-ntfy
      provider:
        type: ntfy
        config: default
        with:
          message: "test"`;

describe("workflow YAML import validation", () => {
  it("rejects a workflow whose `with:` is a sibling of `provider:`", () => {
    const error = validateImportedWorkflow(MISPLACED_WITH);

    expect(error).not.toBeNull();
    // The message must name the offending key so the user can act on it.
    expect(error).toContain("with");
  });

  it("accepts the same workflow once `with:` is nested under `provider:`", () => {
    // Guard rail: validation must reject only the misplacement, not the shape.
    expect(validateImportedWorkflow(NESTED_WITH)).toBeNull();
  });

  it("the misplaced form is exactly what every consumer would read as empty", () => {
    // Shows why silently accepting it is harmful: `provider.with` — the path the
    // backend parser and the UI both read — is undefined, while the parameters
    // sit unreachable at step level.
    const parsed: any = parseWorkflowYamlToJSON(MISPLACED_WITH);
    expect(parsed.success).toBe(false);

    const raw: any = require("yaml").parse(MISPLACED_WITH);
    const action = raw.workflow.actions[0];
    expect(action.provider.with).toBeUndefined();
    expect(action.with).toEqual({ message: "test" });
  });
});
