import { NextApiRequest, NextApiResponse } from "next";
import {
  CopilotRuntime,
  OpenAIAdapter,
  copilotRuntimeNextJSPagesRouterEndpoint,
} from "@copilotkit/runtime";
import OpenAI from "openai";

const openai = new OpenAI({
  organization: process.env.OPEN_AI_ORGANIZATION_ID,
  apiKey: process.env.OPEN_AI_API_KEY,
});

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    const serviceAdapter = new OpenAIAdapter({ openai });
    const runtime = new CopilotRuntime();

    const handleRequest = copilotRuntimeNextJSPagesRouterEndpoint({
      endpoint: "/api/copilotkit",
      runtime,
      serviceAdapter,
    });
    await handleRequest(req, res);
  } catch (error) {
    console.error("Error handling request:", error);
    res.status(500).json({
      error: "An internal server error occurred. Please try again later.",
    });
  }
}
