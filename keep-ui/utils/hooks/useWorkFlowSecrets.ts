import { useState } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";
import useSWR from "swr";

export function useSecrets(workflowId: string) {
  const api = useApi();
  const [error, setError] = useState<string>("");

  const getSecrets = useSWR<{ [key: string]: string }>(
    api.isReady() ? `/workflows/${workflowId}/secrets` : null,
    (url: string) => api.get(url)
  );

  const addOrUpdateSecret = async (
    secrets: { [key: string]: string },
    newSecretKey: string,
    newSecretValue: string
  ) => {
    try {
      const updatedSecrets = { ...secrets, [newSecretKey]: newSecretValue };
      await api.post(`/workflows/${workflowId}/secrets`, {
        [newSecretKey]: newSecretValue,
      });
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to write secret");
    }
  };

  const deleteSecret = async (name: string) => {
    try {
      await api.delete(`/workflows/${workflowId}/secrets/${name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete secret");
    }
  };

  return { getSecrets, error, addOrUpdateSecret, deleteSecret };
}
