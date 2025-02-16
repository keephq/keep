import { Button, TextInput } from "@/components/ui";
import Modal from "@/components/ui/Modal";
import { KeepApiError } from "@/shared/api";
import { useApi } from "@/shared/lib/hooks/useApi";
import { ResultJsonCard } from "@/shared/ui";
import { Callout, Subtitle, Title, Text } from "@tremor/react";
import { useState } from "react";

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
  const api = useApi();
  const [isOpen, setIsOpen] = useState(false);
  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const [result, setResult] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);

  function handleRun(
    e: React.FormEvent<HTMLFormElement> | React.MouseEvent<HTMLButtonElement>
  ) {
    e.preventDefault();
    async function invokeMethod() {
      try {
        setIsLoading(true);
        setErrors({});
        const responseObject = await api.post(
          `/providers/${providerInfo.provider_id}/invoke/${method}`,
          {
            ...methodParams,
            providerInfo: {
              provider_id: providerInfo.provider_id,
              provider_type: providerInfo.provider_type,
            },
          }
        );
        setResult(responseObject);
      } catch (e: any) {
        setErrors({
          [e.message]:
            e instanceof KeepApiError
              ? [e.responseJson?.error_msg, e.proposedResolution].join(".\n")
              : "Unknown error invoking method",
        });
      } finally {
        setIsLoading(false);
      }
    }
    invokeMethod();
  }

  return (
    <>
      <Button
        variant="secondary"
        color="orange"
        size="sm"
        onClick={(e) => {
          setIsOpen(true);
          handleRun(e);
        }}
      >
        Test step
      </Button>
      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)}>
        <form className="flex flex-col gap-5" onSubmit={handleRun}>
          <div>
            <Title>Test Step</Title>
            <Subtitle>Test the step with chosen parameters</Subtitle>
          </div>
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
