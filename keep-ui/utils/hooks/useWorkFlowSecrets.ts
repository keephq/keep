import { useState } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";

interface Secret {
  name: string;
  value: string;
}

export function useSecrets(workflowId: string) {
  const api = useApi();
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [error, setError] = useState<string>("");

  const addOrUpdateSecret = async (name: string, value: string) => {
    try {
      const resp = await api.post(
        `/workflows/${workflowId}/secrets?secret_name=${name}&secret_value=${value}`
      );
      console.log("resp",resp);
      setSecrets((prev) => [...prev.filter((s) => s.name !== name), { name, value }]);
      setError("");
    } catch (err) {
      console.log("err",err);
      setError(err instanceof Error ? err.message : "Failed to write secret");
    }
  };

  const readSecret = async (name: string, isJson = false) => {
    try {
      const secretValue = await api.get(`/workflows/${workflowId}/secrets/${name}`, {
        params: { is_json: isJson },
      });

      setSecrets((prev) => [...prev.filter((s) => s.name !== name), { name, value: secretValue }]);

      return secretValue;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to read secret");
      return null;
    }
  };

  const deleteSecret = async (name: string) => {
    try {
      await api.delete(`/workflows/${workflowId}/secrets/${name}`);

      setSecrets((prev) => prev.filter((s) => s.name !== name));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete secret");
    }
  };

  return { secrets, error, addOrUpdateSecret, readSecret, deleteSecret };
}
