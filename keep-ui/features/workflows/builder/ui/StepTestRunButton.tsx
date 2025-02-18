import { Button, TextInput } from "@/components/ui";
import Modal from "@/components/ui/Modal";
import { useApi } from "@/shared/lib/hooks/useApi";
import { ResultJsonCard } from "@/shared/ui";
import { Callout, Subtitle, Title, Text } from "@tremor/react";
import { useState } from "react";

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

export function StepTestRunButton({
  providerInfo,
  method,
  methodParams,
  updateProperty,
}: {
  providerInfo: { provider_id: string; provider_type: string };
  method: "_query" | "_notify";
  methodParams: Record<string, any>;
  updateProperty: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  const testStep = useTestStep();
  const [isOpen, setIsOpen] = useState(false);
  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const [result, setResult] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);

  function handleRun(
    e: React.FormEvent<HTMLFormElement> | React.MouseEvent<HTMLButtonElement>
  ) {
    e.preventDefault();
    const handleTestStep = async () => {
      try {
        setIsLoading(true);
        const result = await testStep(providerInfo, method, methodParams);
        setResult(result);
      } catch (e: unknown) {
        setErrors({
          error: e instanceof Error ? e.message : "Failed to test step",
        });
      } finally {
        setIsLoading(false);
      }
    };
    handleTestStep();
  }

  return (
    <>
      <Button
        variant="secondary"
        color="orange"
        size="sm"
        onClick={() => {
          setIsOpen(true);
        }}
        disabled={
          isLoading ||
          !Object.keys(methodParams).length ||
          !providerInfo.provider_id ||
          !providerInfo.provider_type
        }
      >
        Test step
      </Button>
      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)}>
        <form className="flex flex-col gap-5" onSubmit={handleRun}>
          <div>
            <Title>Test Step</Title>
            <Subtitle>Test the step with chosen parameters</Subtitle>
          </div>
          <Callout title="Step parameters">
            Changing the parameters here will change properties of the step.
          </Callout>
          {methodParams &&
            Object.entries(methodParams).map(([key, value]) => (
              <div key={key}>
                <Text>{key}</Text>
                <TextInput
                  value={value}
                  id={key}
                  name={key}
                  onChange={updateProperty}
                />
              </div>
            ))}
          {errors &&
            Object.values(errors).length > 0 &&
            Object.entries(errors).map(([key, error]) => (
              <Callout key={key} title={key} color="red">
                {error}
              </Callout>
            ))}
          <div>{result && <ResultJsonCard result={result} />}</div>
          <div className="flex justify-end mt-4 gap-2">
            <Button
              onClick={() => setIsOpen(false)}
              color="orange"
              variant="secondary"
            >
              Cancel
            </Button>
            <Button variant="primary" color="orange" disabled={isLoading}>
              {isLoading ? "Running..." : "Run"}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
