import { useState, useEffect } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";

interface Secrets {
  [key: string]: string; // Store secrets as key-value pairs inside an object
}

export function useSecrets(workflowId: string) {
  const api = useApi();
  const [secrets, setSecrets] = useState<Secrets>({});
  const [error, setError] = useState<string>("");

  // Fetch secrets on mount
  useEffect(() => {
    fetchSecrets();
  }, [workflowId]);

  const fetchSecrets = async () => {
    try {
      const resp = await api.get(`/workflows/${workflowId}/secrets`);
      setSecrets(resp || {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch secrets");
    }
  };

  const addOrUpdateSecret = async (name: string, value: string) => {
    try {
      const updatedSecrets = { ...secrets, [name]: value };
      await api.post(`/workflows/${workflowId}/secrets`, {
        [name]: value,
      });
      setSecrets(updatedSecrets);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to write secret");
    }
  };

  const deleteSecret = async (name: string) => {
    try {
      await api.delete(`/workflows/${workflowId}/secrets/${name}`);
      const updatedSecrets = { ...secrets };
      delete updatedSecrets[name];
      setSecrets(updatedSecrets);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete secret");
    }
  };

  return { secrets, error, addOrUpdateSecret, deleteSecret };
}
