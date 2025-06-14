import { useCallback, useState } from "react";
import { parseDocument } from "yaml";
import type { editor, Uri } from "monaco-editor";
import { MarkerSeverity, getSeverityString } from "./utils";
import {
  YamlValidationError,
  YamlValidationErrorSeverity,
} from "../model/types";
import { validateMustacheVariableForYAMLStep } from "@/entities/workflows/lib/validate-mustache-yaml";
import {
  getCurrentPath,
  parseWorkflowYamlStringToJSON,
} from "@/entities/workflows/lib/yaml-utils";
import { useProviders } from "@/utils/hooks/useProviders";

interface UseYamlValidationProps {
  onValidationErrors?: React.Dispatch<
    React.SetStateAction<YamlValidationError[]>
  >;
}

const SEVERITY_MAP = {
  error: MarkerSeverity.Error,
  warning: MarkerSeverity.Warning,
  info: MarkerSeverity.Hint,
};

export interface UseYamlValidationResult {
  validationErrors: YamlValidationError[] | null;
  validateMustacheExpressions: (
    model: editor.ITextModel | null,
    monaco: typeof import("monaco-editor") | null,
    secrets: Record<string, string>
  ) => void;
  handleMarkersChanged: (
    editor: editor.IStandaloneCodeEditor,
    modelUri: Uri,
    markers: editor.IMarker[] | editor.IMarkerData[],
    owner: string
  ) => void;
}

export function useYamlValidation({
  onValidationErrors,
}: UseYamlValidationProps): UseYamlValidationResult {
  const [validationErrors, setValidationErrors] = useState<
    YamlValidationError[] | null
  >(null);

  const { data: { providers, installed_providers: installedProviders } = {} } =
    useProviders();

  // Function to find the current step in the workflow based on the path
  const findStepFromPath = useCallback((path: (string | number)[]) => {
    if (!path || path.length < 3) {
      return null;
    }

    // Look for 'steps' in the path
    const stepsIdx = path.findIndex((p) => p === "steps");
    if (stepsIdx === -1) {
      return null;
    }

    // Check if there's an index after 'steps'
    if (stepsIdx + 1 >= path.length || typeof path[stepsIdx + 1] !== "number") {
      return null;
    }

    return {
      stepIndex: path[stepsIdx + 1] as number,
      isInStep: true,
    };
  }, []);

  const findActionFromPath = useCallback((path: (string | number)[]) => {
    if (!path || path.length < 3) {
      return null;
    }

    // Look for 'actions' in the path
    const actionsIdx = path.findIndex((p) => p === "actions");
    if (actionsIdx === -1) {
      return null;
    }

    // Check if there's an index after 'actions'
    if (
      actionsIdx + 1 >= path.length ||
      typeof path[actionsIdx + 1] !== "number"
    ) {
      return null;
    }

    return {
      actionIndex: path[actionsIdx + 1] as number,
      isInAction: true,
    };
  }, []);

  // Function to validate mustache expressions and apply decorations
  const validateMustacheExpressions = useCallback(
    (
      model: editor.ITextModel | null,
      monaco: typeof import("monaco-editor") | null,
      secrets: Record<string, string> = {}
    ) => {
      if (!model || !monaco) {
        return;
      }

      try {
        const text = model.getValue();
        const yamlDoc = parseDocument(text);
        let workflowDefinition;

        try {
          // Parse the YAML to JSON to get the workflow definition
          workflowDefinition = parseWorkflowYamlStringToJSON(text);
        } catch (e) {
          console.warn("Unable to parse YAML for mustache validation", e);
        }

        const mustacheRegex = /\{\{([^}]+)\}\}/g;
        // Collect markers to add to the model
        const markers: editor.IMarkerData[] = [];

        let match;
        while ((match = mustacheRegex.exec(text)) !== null) {
          const fullMatch = match[0]; // The entire {{...}} expression
          const matchStart = match.index;
          const matchEnd = matchStart + fullMatch.length;

          // Get the position (line, column) for the match
          const startPos = model.getPositionAt(matchStart);
          const endPos = model.getPositionAt(matchEnd);

          // Get the current path in the YAML document
          const path = getCurrentPath(yamlDoc, matchStart);

          // Extract step information from the path
          const stepInfo = findStepFromPath(path);
          const actionInfo = findActionFromPath(path);

          const currentStepType = stepInfo?.isInStep ? "step" : "action";
          // Extract the content from the mustache expression (remove {{ and }})
          const variableContent = match[1].trim();

          let errorMessage: string | null = null;
          let severity: YamlValidationErrorSeverity = "warning";

          // If we have both the workflow definition and step info, we can do proper validation
          if (
            workflowDefinition?.workflow &&
            (stepInfo || actionInfo) &&
            (workflowDefinition.workflow.steps ||
              workflowDefinition.workflow.actions)
          ) {
            const currentStep = stepInfo?.isInStep
              ? workflowDefinition.workflow.steps[stepInfo.stepIndex]
              : actionInfo?.isInAction
                ? workflowDefinition.workflow.actions[actionInfo.actionIndex]
                : null;

            if (currentStep) {
              const result = validateMustacheVariableForYAMLStep(
                variableContent,
                currentStep,
                currentStepType,
                workflowDefinition.workflow,
                secrets ?? {},
                providers ?? null,
                installedProviders ?? null
              );

              if (result) {
                errorMessage = result[0];
                severity = result[1] as YamlValidationErrorSeverity;
              }
            }
          } else {
            // Fallback to basic validation when we don't have full context
            const parts = variableContent.split(".");
            const hasEmptyParts = parts.some(
              (part: string) => !part || part.trim() === ""
            );

            if (hasEmptyParts) {
              errorMessage = `Invalid mustache variable: '${variableContent}' - Parts cannot be empty.`;
              severity = "error";
            }
            // Add warnings for variables we can't fully validate
            else if (
              !workflowDefinition &&
              (variableContent.startsWith("steps.") ||
                variableContent.startsWith("secrets.") ||
                variableContent.startsWith("alert.") ||
                variableContent.startsWith("incident."))
            ) {
              errorMessage = `Warning: Unable to fully validate mustache variable '${variableContent}' without complete workflow context.`;
              severity = "warning";
            }
          }

          // Add marker for validation issues
          if (errorMessage) {
            markers.push({
              severity: SEVERITY_MAP[severity],
              message: errorMessage,
              startLineNumber: startPos.lineNumber,
              startColumn: startPos.column,
              endLineNumber: endPos.lineNumber,
              endColumn: endPos.column,
              source: "mustache-validation",
            });
          }
        }

        // Set markers on the model for the problems panel
        monaco.editor.setModelMarkers(model, "mustache-validation", markers);
      } catch (error) {
        console.error("Error validating mustache expressions:", error);
      }
    },
    [findStepFromPath, findActionFromPath, providers, installedProviders]
  );

  const handleMarkersChanged = useCallback(
    (
      editor: editor.IStandaloneCodeEditor,
      modelUri: Uri,
      markers: editor.IMarker[] | editor.IMarkerData[],
      owner: string
    ) => {
      const editorUri = editor.getModel()?.uri;
      if (modelUri.path !== editorUri?.path) {
        return;
      }

      const errors: YamlValidationError[] = [];
      for (const marker of markers) {
        errors.push({
          message: marker.message,
          severity: getSeverityString(marker.severity as MarkerSeverity),
          lineNumber: marker.startLineNumber,
          column: marker.startColumn,
          owner,
        });
      }
      const errorsUpdater = (prevErrors: YamlValidationError[] | null) => {
        const prevOtherOwners = prevErrors?.filter((e) => e.owner !== owner);
        return [...(prevOtherOwners ?? []), ...errors];
      };
      setValidationErrors(errorsUpdater);
      onValidationErrors?.(errorsUpdater);
    },
    [onValidationErrors]
  );

  return {
    validationErrors,
    validateMustacheExpressions,
    handleMarkersChanged,
  };
}
