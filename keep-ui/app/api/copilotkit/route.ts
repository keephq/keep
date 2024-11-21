import {
  CopilotRuntime,
  OpenAIAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import OpenAI, { OpenAIError } from "openai";
import { NextRequest } from "next/server";

function initializeCopilotRuntime() {
  try {
    const openai = new OpenAI({
      organization: process.env.OPEN_AI_ORGANIZATION_ID,
      apiKey: process.env.OPEN_AI_API_KEY,
    });
    const serviceAdapter = new OpenAIAdapter({ openai });
    const runtime = new CopilotRuntime();
    return { runtime, serviceAdapter };
  } catch (error) {
    if (error instanceof OpenAIError) {
      console.log("Error connecting to OpenAI", error);
    } else {
      console.error("Error initializing Copilot Runtime", error);
    }
    return null;
  }
}

const runtimeOptions = initializeCopilotRuntime();

export const POST = async (req: NextRequest) => {
  if (!runtimeOptions) {
    return new Response("Error initializing Copilot Runtime", { status: 500 });
  }
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime: runtimeOptions.runtime,
    serviceAdapter: runtimeOptions.serviceAdapter,
    endpoint: "/api/copilotkit",
  });

  return handleRequest(req);
};
