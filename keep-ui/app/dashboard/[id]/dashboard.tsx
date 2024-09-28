"use client";

import React, { useEffect, useRef } from "react";
import { embedDashboard } from "@superset-ui/embedded-sdk";
import { getApiURL } from "utils/apiUrl";
import { useSession } from "next-auth/react";
import { Card } from "@mui/material";

const DashboardPage = () => {
  const { data: session } = useSession();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!session || !session.accessToken) {
      return; // Exit early if not logged in or no access token
    }

    const embedDashboardFunc = async () => {
      if (containerRef.current) {
        await embedDashboard({
          id: "06f05307-b253-4e8f-affd-15bb4228082d", // Replace with your actual dashboard ID
          supersetDomain: "http://localhost:8088", // Replace with your Superset domain
          mountPoint: containerRef.current,
          fetchGuestToken: () =>
            fetchGuestTokenFromBackend(session.accessToken),
          dashboardUiConfig: {
            hideTitle: true,
            hideTab: true,
            hideChartControls: true,
            filters: {
              expanded: false,
            },
          },
        });

        // Hack to make the view 100% in height and width
        if (containerRef.current.children[0] instanceof HTMLElement) {
          containerRef.current.children[0].style.width = "100%";
          containerRef.current.children[0].style.height = "100%";
        }
      }
    };

    embedDashboardFunc();
  }, [session]);

  const fetchGuestTokenFromBackend = async (accessToken: string) => {
    const apiUrl = getApiURL();
    const response = await fetch(`${apiUrl}/dashboard/token`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });
    const data = await response.json();
    return data.token;
  };

  if (!session) {
    return <div>Loading...</div>;
  }

  return (
    <Card
      sx={{
        width: "100%",
        height: "100vh",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        id="my-superset-container"
        ref={containerRef}
        style={{ flexGrow: 1, width: "100%", height: "100%" }}
      ></div>
    </Card>
  );
};

export default DashboardPage;
