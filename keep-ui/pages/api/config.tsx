import type { NextApiRequest, NextApiResponse } from "next";

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const gitBranchName = process.env.VERCEL_GIT_COMMIT_REF || "notvercel";
  if(gitBranchName === "main" || gitBranchName === "notvercel"){
    res.status(200).json({
      AUTH_TYPE: process.env.AUTH_TYPE,
      PUSHER_DISABLED: process.env.PUSHER_DISABLED === "true",
      API_URL: process.env.API_URL
    });
    return;
  }
  let branchNameSanitized = gitBranchName.replace(/\//g, '-').substring(0, 63);
  let serviceName = `keep-api-${branchNameSanitized}`;
  if (serviceName.length > 63) {
    serviceName = serviceName.substring(0, 49);
  }

  if (serviceName.endsWith('-')) {
    serviceName = serviceName.slice(0, -1);
  }
  let apiUrl = process.env.API_URL!.replace('keep-api', serviceName);
  res.status(200).json({
    AUTH_TYPE: process.env.AUTH_TYPE,
    PUSHER_DISABLED: process.env.PUSHER_DISABLED === "true",
    API_URL: apiUrl
  });
}
