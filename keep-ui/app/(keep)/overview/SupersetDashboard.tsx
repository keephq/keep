"use client";

import { useEffect, useRef, useState } from "react";
import { embedDashboard, EmbeddedDashboard } from "@superset-ui/embedded-sdk";
import { useSupersetToken } from "@/utils/hooks/useSupersetToken";
import { Loader2 } from "lucide-react";
import { useSupersetDashboards } from "@/utils/hooks/useSupersetDashboards";
import { useConfig } from "@/utils/hooks/useConfig";

interface SupersetDashboardProps {
  dashboardId: string;
}

export function SupersetDashboard({ dashboardId }: SupersetDashboardProps) {
  const { data: config } = useConfig();
  const { token, isLoading, error } = useSupersetToken({ dashboardId });
  const containerRef = useRef<HTMLDivElement>(null);
  const dashboardRef = useRef<EmbeddedDashboard | null>(null);
  const [authError, setAuthError] = useState<boolean>(false);
  const {
    dashboards,
    error: dashboardError,
    isLoading: dashboardIsLoading,
  } = useSupersetDashboards();

  const embeddedId = dashboards.find((d) => d.id === dashboardId)?.uuid;

  useEffect(() => {
    if (authError) {
      // Refresh the page if we detect an auth error
      window.location.reload();
    }
  }, [authError]);

  useEffect(() => {
    if (!token || !containerRef.current || dashboardRef.current) return;

    const embedDashboardFunc = async () => {
      const mountPoint = containerRef.current;
      if (!mountPoint) return;

      try {
        const dashboard = await embedDashboard({
          id: embeddedId!,
          // if no config.KEEP_SUPERSET_URL, the navbar will not render the menu anyway
          // so we don't need to check for it here
          supersetDomain: config?.KEEP_SUPERSET_URL!,
          mountPoint,
          fetchGuestToken: () => Promise.resolve(token),
          dashboardUiConfig: {
            hideTitle: true,
            hideTab: false,
            hideChartControls: false,
            filters: {
              visible: true,
              expanded: true,
            },
          },
        });

        dashboardRef.current = dashboard;

        if (mountPoint.children[0] instanceof HTMLElement) {
          mountPoint.children[0].style.width = "100%";
          mountPoint.children[0].style.height = "100%";
        }
      } catch (err) {
        console.error("Error embedding dashboard:", err);
        // Check if the error is a SupersetApiError with "Not authorized" message
        if (
          err instanceof Error &&
          err.message.includes("SupersetApiError: Not authorized")
        ) {
          console.log("Token expired, refreshing page...");
          setAuthError(true);
        }
      }
    };

    embedDashboardFunc();

    return () => {
      if (dashboardRef.current) {
        dashboardRef.current = null;
      }
    };
  }, [token, embeddedId, authError]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
          <span className="text-gray-600">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-lg text-red-500">
          Error loading dashboard: {error.message}
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="w-full h-full bg-white rounded-lg shadow-lg"
    />
  );
}
