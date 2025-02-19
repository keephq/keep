import { Button, TextInput } from "@/components/ui";
import { useApi } from "@/shared/lib/hooks/useApi";
import { JsonCard } from "@/shared/ui";
import { Callout, Text } from "@tremor/react";
import { useMemo, useState } from "react";
import { EditorLayout } from "./StepEditor";
import { Editor } from "@monaco-editor/react";

export function useTestStep() {
  const api = useApi();
  async function testStep(
    providerInfo: { provider_id: string; provider_type: string },
    method: "_query" | "_notify",
    methodParams: Record<string, any>
  ) {
    return await api.post(
      `/providers/${providerInfo.provider_id}/invoke/${method}`,
      {
        ...methodParams,
        providerInfo: {
          provider_id: providerInfo.provider_id,
          provider_type: providerInfo.provider_type,
        },
      }
    );
  }

  return testStep;
}

const variablesRegex = /{{.*?}}/g;

export function TestRunStepForm({
  providerInfo,
  method,
  methodParams,
}: {
  providerInfo: { provider_id: string; provider_type: string };
  method: "_query" | "_notify";
  methodParams: Record<string, any>;
}) {
  const testStep = useTestStep();
  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const [result, setResult] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Todo: find {{variables}} in the formData with regex, and store them in a dict [variable_name: ""]
  const variables = useMemo(() => {
    return Object.values(methodParams)
      .map((value) => value.toString().match(variablesRegex))
      .filter((variable) => variable !== null)
      .map((variable) => variable[0].replace(/{{|}}/g, ""))
      .reduce((acc, key) => {
        acc[key] = "";
        return acc;
      }, {});
  }, [methodParams]);

  const [variablesOverride, setVariablesOverride] = useState<
    Record<string, string>
  >({});

  const resultingParameters = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(methodParams).map(([key, value]) => {
          const variableMatch = value.toString().match(variablesRegex);
          const variableName = variableMatch?.[0].replace(/{{|}}/g, "");
          if (variableName && variablesOverride[variableName]) {
            return [
              key,
              value.replace(
                `{{${variableName}}}`,
                variablesOverride[variableName]
              ),
            ];
          }
          return [key, value];
        })
      ),
    [methodParams, variablesOverride]
  );

  function handleRun(
    e: React.FormEvent<HTMLFormElement> | React.MouseEvent<HTMLButtonElement>
  ) {
    e.preventDefault();
    const handleTestStep = async () => {
      try {
        setIsLoading(true);
        setErrors({});
        const result = await testStep(
          providerInfo,
          method,
          resultingParameters
        );
        setResult(result);
      } catch (e: unknown) {
        const errorMessage = e instanceof Error ? e.message : "Unknown error";
        setErrors({
          "Failed to test step": errorMessage,
        });
      } finally {
        setIsLoading(false);
      }
    };
    handleTestStep();
  }

  const isDisabled = Object.values(methodParams).every((value) => !value);

  return (
    <form className="h-full flex flex-col" onSubmit={handleRun}>
      <EditorLayout className="flex-1 flex flex-col gap-5">
        {Object.values(variables).length > 0 && (
          <section>
            <Text className="font-bold mb-2">Override variables</Text>
            <Text className="mb-2">
              Your parameters use the following variables. You can override
              them, it only applies to this test run.
            </Text>
            <ul className="flex flex-col gap-2">
              {Object.entries(variables).map(([varName, value]) => (
                <li key={varName} className="flex flex-col gap-1">
                  <code className="whitespace-pre-wrap text-sm">{`${varName} =`}</code>
                  <TextInput
                    value={variablesOverride[varName] ?? ""}
                    onChange={(e) =>
                      setVariablesOverride({
                        ...variablesOverride,
                        [varName]: e.target.value,
                      })
                    }
                  />
                </li>
              ))}
            </ul>
          </section>
        )}
        <section>
          <Text className="font-bold mb-2">Provider and parameters</Text>
          {Object.values(variablesOverride).some((value) => value) && (
            <Text className="mb-2">
              The parameters after the variables are overridden.
            </Text>
          )}
          <div>
            <JsonCard title="Provider configuration" json={providerInfo} />
            <JsonCard title="Parameters" json={resultingParameters} />
          </div>
        </section>
        <section>
          <Text className="font-bold mb-2">Result</Text>
          <Text className="mb-2">
            The result of the test run will be displayed here.
          </Text>
          {result && (
            <pre
              className="bg-gray-100 rounded-md overflow-hidden text-xs my-2"
              ref={(el) => {
                if (el) {
                  el.scrollIntoView({ behavior: "smooth", block: "start" });
                }
              }}
            >
              <div className="text-gray-500 bg-gray-50 p-2">Result</div>
              <div
                className="overflow-auto bg-[#fffffe] break-words whitespace-pre-wrap py-2 border rounded-[inherit] rounded-t-none  border-gray-200"
                style={{
                  height: Math.min(
                    JSON.stringify(result, null, 2).split("\n").length * 20 +
                      16,
                    192
                  ),
                }}
              >
                <Editor
                  value={JSON.stringify(result, null, 2)}
                  language="json"
                  theme="vs-light"
                  options={{
                    readOnly: true,
                    minimap: { enabled: false },
                    scrollBeyondLastLine: false,
                    fontSize: 12,
                    lineNumbers: "off",
                    folding: true,
                    wordWrap: "on",
                  }}
                />
              </div>
            </pre>
          )}
        </section>
        {errors &&
          Object.values(errors).length > 0 &&
          Object.entries(errors).map(([key, error]) => (
            <Callout
              key={key}
              title={key}
              color="red"
              ref={(el) => {
                if (el) {
                  el.scrollIntoView({ behavior: "smooth", block: "start" });
                }
              }}
            >
              {error}
            </Callout>
          ))}
      </EditorLayout>
      <div className="sticky flex justify-end bottom-0 px-4 py-2.5 bg-white border-t border-gray-200">
        <Button
          variant="primary"
          className="w-full"
          color="orange"
          disabled={isLoading || isDisabled}
        >
          {isLoading ? "Running..." : "Test Run"}
        </Button>
      </div>
    </form>
  );
}
