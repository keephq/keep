import {
    V2Step,
    ReactFlowDefinition,
} from "app/workflows/builder/builder-store";
import {
    stepValidatorV2,
    globalValidatorV2,
} from "app/workflows/builder/builder-validators";
import {
    wrapDefinitionV2,
    parseWorkflow,
} from "app/workflows/builder/utils";
import { Provider } from "app/providers/providers";
import { Definition } from "app/workflows/builder/builder-store";
import { Workflow } from "app/workflows/models";

export default function useWorklowValidator(
    workflow: Workflow,
    providers: Provider[] | null
) {

    let errorMessage = null;
    const setStepValidationErrorV2 = (step: V2Step, error: string | null) => {
        errorMessage = error;
    };

    const setGlobalValidationErrorV2 = (
        id: string | null,
        error: string | null
    ) => {
        errorMessage = error;
    };

    const ValidatorConfigurationV2: {
        step: (
            step: V2Step,
            parent?: V2Step,
            definition?: ReactFlowDefinition
        ) => boolean;
        root: (def: Definition) => boolean;
    } = {
        step: (step, parent, definition) =>
            stepValidatorV2(step, setStepValidationErrorV2, parent, definition),
        root: (def) => globalValidatorV2(def, setGlobalValidationErrorV2),
    };

    if (!workflow || !providers) {
        return {
            loading: true,
            isValid: true,
            error: errorMessage
        }
    }
    const defintion = wrapDefinitionV2({
        ...parseWorkflow(workflow?.workflow_raw, providers, true),
        isValid: true,
    });
    const { sequence, properties } = defintion.value ?? { sequence: [], properties: {} };
    let isValid = true;
    for (let step of sequence) {
        isValid = ValidatorConfigurationV2?.step(step);
        if (!isValid) {
            break;
        }
    }

    if (!isValid) {
        return {
            loading: false,
            isValid: false,
            error: errorMessage
        };
    }

    isValid = ValidatorConfigurationV2.root({ sequence, properties });

    return {
        loading: false,
        isValid,
        error: errorMessage
    };
}

