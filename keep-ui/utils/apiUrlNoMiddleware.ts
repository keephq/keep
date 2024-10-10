"use client";

import { useConfig } from "utils/hooks/useConfig";

function getApiURL(): string {
  const componentType = typeof window === "undefined" ? "server" : "client";

  if (componentType === "client") {
    return "/backend";
  }

  // SERVER ONLY FROM HERE ON
  const gitBranchName = process.env.VERCEL_GIT_COMMIT_REF || "notvercel";

  if (gitBranchName === "main" || gitBranchName === "notvercel") {
    return process.env.API_URL!;
  } else {
    console.log("preview branch on vercel");
    let branchNameSanitized = gitBranchName
      .replace(/\//g, "-")
      .substring(0, 63);
    let serviceName = `keep-api-${branchNameSanitized}`;
    if (serviceName.length > 63) {
      serviceName = serviceName.substring(0, 49);
    }

    if (serviceName.endsWith("-")) {
      serviceName = serviceName.slice(0, -1);
    }
    return process.env.API_URL!.replace("keep-api", serviceName);
  }
}

export function getApiUrlNoMiddleware(): string {
  const componentType = typeof window === "undefined" ? "server" : "client";

  if (componentType === "client") {
    const { data: configData } = useConfig();
    return configData?.API_URL!;
  }

  // SERVER ONLY FROM HERE ON
  return getApiURL();
}
