import { parseWorkflow } from "@/entities/workflows/lib/parser";
import {
  validateGlobalPure,
  validateStepPure,
} from "@/entities/workflows/model/validation";
import { Provider } from "@/shared/api/providers";
import { useProviders } from "@/utils/hooks/useProviders";
import { useCallback } from "react";

// [stepId, error, type = "error" | "warning"]
export type StepValidationError = [string, string, "error" | "warning"];

function validateYAML(
  yamlString: string,
  providers: Provider[],
  installedProviders: Provider[]
) {
  try {
    const definition = parseWorkflow(yamlString, providers);
    let isValid = true;
    const validationErrors: StepValidationError[] = [];
    const result = validateGlobalPure(definition);
    if (result) {
      result.forEach(([key, error]) => {
        validationErrors.push([key, error, "error"]);
      });
      isValid = result.length === 0;
    }

    // Check each step's validity
    for (const step of definition.sequence) {
      const errors = validateStepPure(
        step,
        providers,
        installedProviders,
        definition
      );
      if (step.componentType === "switch") {
        [...step.branches.true, ...step.branches.false].forEach((branch) => {
          const errors = validateStepPure(
            branch,
            providers,
            installedProviders,
            definition
          );
          if (errors.length > 0) {
            errors.forEach(([error, type]) => {
              validationErrors.push([branch.name || branch.id, error, type]);
            });
            isValid = false;
          }
        });
      }
      if (step.componentType === "container") {
        step.sequence.forEach((s) => {
          const errors = validateStepPure(
            s,
            providers,
            installedProviders,
            definition
          );
          if (errors.length > 0) {
            errors.forEach(([error, type]) => {
              validationErrors.push([s.name || s.id, error, type]);
            });
            isValid = false;
          }
        });
      }
      if (errors.length > 0) {
        errors.forEach(([error, type]) => {
          validationErrors.push([step.name || step.id, error, type]);
        });
        isValid = false;
      }
    }

    // We allow deployment even if there are
    // - provider errors, as the user can fix them later
    // - variable errors, as the user can fix them later
    const canDeploy =
      validationErrors.filter(
        ([_, error]) =>
          !error.includes("provider") && !error.startsWith("Variable:")
      ).length === 0;

    return {
      isValid,
      canDeploy,
      validationErrors,
    };
  } catch (error) {
    const unknownError: StepValidationError = [
      "yaml",
      error instanceof Error ? error.message : "Unknown error",
      "error",
    ];
    return {
      isValid: false,
      canDeploy: false,
      validationErrors: [unknownError],
    };
  }
}

export function useGetYamlValidationErrors() {
  const {
    data: { providers, installed_providers: installedProviders } = {},
    isLoading,
  } = useProviders();

  return useCallback(
    (yamlString: string) => {
      return validateYAML(
        yamlString,
        providers ?? [],
        installedProviders ?? []
      );
    },
    [providers, installedProviders]
  );
}

export function YAMLValidationErrors({
  validationErrors,
}: {
  validationErrors: StepValidationError[];
}) {
  return (
    <div className="">
      {validationErrors.map(([stepId, error, type]) => (
        <div
          key={stepId + error + type}
          className={type === "error" ? "bg-red-100" : "bg-yellow-100"}
        >
          {stepId} - {error} - {type}
        </div>
      ))}
    </div>
  );
}
