import { TopologyApplication } from "./models";
import useSWR, { SWRConfiguration } from "swr";
import { useCallback, useMemo } from "react";
import { useTopology } from "./useTopology";
import { useRevalidateMultiple } from "@/utils/state";
import { TOPOLOGY_URL } from "./useTopology";
import { KeepApiError } from "@/shared/api";
import { useApi } from "@/shared/lib/hooks/useApi";

type UseTopologyApplicationsOptions = {
  initialData?: TopologyApplication[];
  options?: SWRConfiguration;
};

export const TOPOLOGY_APPLICATIONS_URL = `/topology/applications`;

export function useTopologyApplications(
  { initialData, options }: UseTopologyApplicationsOptions = {
    options: {
      revalidateOnFocus: false,
    },
  }
) {
  const api = useApi();
  const revalidateMultiple = useRevalidateMultiple();
  const { topologyData, mutate: mutateTopology } = useTopology();
  const { data, error, isLoading, mutate } = useSWR<TopologyApplication[]>(
    TOPOLOGY_APPLICATIONS_URL,
    (url) => api.get(url),
    {
      fallbackData: initialData,
      ...options,
    }
  );

  const applications = useMemo(() => data ?? [], [data]);

  const addApplication = useCallback(
    async (application: Omit<TopologyApplication, "id">) => {
      try {
        const result = await api.post("/topology/applications", application);
        revalidateMultiple([TOPOLOGY_URL, TOPOLOGY_APPLICATIONS_URL]);
        return result as TopologyApplication;
      } catch (error) {
        // Rollback optimistic update on error
        throw new Error("Failed to add application", {
          cause:
            error instanceof KeepApiError ? error.message : "Unknown error",
        });
      }
    },
    [api, revalidateMultiple]
  );

  const updateApplication = useCallback(
    async (application: TopologyApplication) => {
      mutate(
        applications.map((app) =>
          app.id === application.id ? application : app
        ),
        false
      );
      if (topologyData) {
        mutateTopology(
          topologyData.map((node) => {
            if (
              application.services.some((service) =>
                node.application_ids.includes(service.service)
              )
            ) {
              return {
                ...node,
                application_ids: node.application_ids.concat(application.id),
              };
            }
            return node;
          })
        );
      }
      try {
        const result = await api.put(
          `/topology/applications/${application.id}`,
          application
        );
        revalidateMultiple([TOPOLOGY_URL, TOPOLOGY_APPLICATIONS_URL]);
        return result as TopologyApplication;
      } catch (error) {
        // Rollback optimistic update on error
        mutate(applications, false);
        mutateTopology(topologyData, false);
        throw new Error("Failed to update application", {
          cause:
            error instanceof KeepApiError ? error.message : "Unknown error",
        });
      }
    },
    [
      api,
      applications,
      mutate,
      mutateTopology,
      revalidateMultiple,
      topologyData,
    ]
  );

  const deleteApplication = useCallback(
    async (applicationId: string) => {
      mutate(
        applications.filter((app) => app.id !== applicationId),
        false
      );
      if (topologyData) {
        mutateTopology(
          topologyData.map((node) => {
            if (node.application_ids.includes(applicationId)) {
              return {
                ...node,
                application_ids: node.application_ids.filter(
                  (id) => id !== applicationId
                ),
              };
            } else {
              return node;
            }
          })
        );
      }
      try {
        const result = await api.delete(
          `/topology/applications/${applicationId}`
        );
        revalidateMultiple([TOPOLOGY_URL, TOPOLOGY_APPLICATIONS_URL]);
        return result;
      } catch (error) {
        // Rollback optimistic update on error
        mutate(applications, false);
        mutateTopology(topologyData, false);
        throw new Error("Failed to delete application", {
          cause:
            error instanceof KeepApiError ? error.message : "Unknown error",
        });
      }
    },
    [
      api,
      applications,
      mutate,
      mutateTopology,
      revalidateMultiple,
      topologyData,
    ]
  );

  return {
    applications,
    addApplication,
    updateApplication,
    removeApplication: deleteApplication,
    error,
    isLoading,
  };
}
