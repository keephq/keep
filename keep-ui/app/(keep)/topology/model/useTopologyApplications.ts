import { TopologyApplication } from "./models";
import { useApiUrl } from "utils/hooks/useConfig";
import useSWR, { SWRConfiguration } from "swr";
import { fetcher } from "@/utils/fetcher";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useCallback, useMemo } from "react";
import { useTopology } from "./useTopology";
import { useRevalidateMultiple } from "@/utils/state";
import { TOPOLOGY_URL } from "./useTopology";

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
  const apiUrl = useApiUrl();
  const { data: session } = useSession();
  const revalidateMultiple = useRevalidateMultiple();
  const { topologyData, mutate: mutateTopology } = useTopology();
  const { data, error, isLoading, mutate } = useSWR<TopologyApplication[]>(
    !session ? null : TOPOLOGY_APPLICATIONS_URL,
    (url: string) => fetcher(apiUrl + url, session!.accessToken),
    {
      fallbackData: initialData,
      ...options,
    }
  );

  const applications = useMemo(() => data ?? [], [data]);

  const addApplication = useCallback(
    async (application: Omit<TopologyApplication, "id">) => {
      const response = await fetch(`${apiUrl}/topology/applications`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify(application),
      });
      if (response.ok) {
        console.log("mutating on success");
        revalidateMultiple([TOPOLOGY_URL, TOPOLOGY_APPLICATIONS_URL]);
      } else {
        // Rollback optimistic update on error
        throw new Error("Failed to add application", {
          cause: response.statusText,
        });
      }
      const json = await response.json();
      return json as TopologyApplication;
    },
    [apiUrl, revalidateMultiple, session?.accessToken]
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
      const response = await fetch(
        `${apiUrl}/topology/applications/${application.id}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session?.accessToken}`,
          },
          body: JSON.stringify(application),
        }
      );
      if (response.ok) {
        revalidateMultiple([TOPOLOGY_URL, TOPOLOGY_APPLICATIONS_URL]);
      } else {
        // Rollback optimistic update on error
        mutate(applications, false);
        mutateTopology(topologyData, false);
        throw new Error("Failed to update application", {
          cause: response.statusText,
        });
      }
      return response;
    },
    [
      apiUrl,
      applications,
      mutate,
      mutateTopology,
      revalidateMultiple,
      session?.accessToken,
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
      const response = await fetch(
        `${apiUrl}/topology/applications/${applicationId}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
          },
        }
      );
      if (response.ok) {
        revalidateMultiple([TOPOLOGY_URL, TOPOLOGY_APPLICATIONS_URL]);
      } else {
        // Rollback optimistic update on error
        mutate(applications, false);
        mutateTopology(topologyData, false);
        throw new Error("Failed to delete application", {
          cause: response.statusText,
        });
      }
      return response;
    },
    [
      apiUrl,
      applications,
      mutate,
      mutateTopology,
      revalidateMultiple,
      session?.accessToken,
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
