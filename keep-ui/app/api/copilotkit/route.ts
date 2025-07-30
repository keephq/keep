import {
  CopilotRuntime,
  OpenAIAdapter,
  LangChainAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import OpenAI, { OpenAIError } from "openai";
import { NextRequest } from "next/server";
import { ChatBedrockConverse } from "@langchain/aws";

export const POST = async (req: NextRequest) => {
  function initializeCopilotRuntime() {
    try {
      const provider = process.env.AI_PROVIDER || "openai";
      
      let serviceAdapter;
      
      if (provider === "bedrock") {
        const bedrockModel = new ChatBedrockConverse({
          model: process.env.BEDROCK_MODEL_ID,
          region: process.env.AWS_REGION,
          credentials: {
            accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
            secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
            ...(process.env.AWS_SESSION_TOKEN && {
              sessionToken: process.env.AWS_SESSION_TOKEN,
            }),
          },
        });
        
        serviceAdapter = new LangChainAdapter({
          chainFn: async ({ messages }) => {
            const response = await bedrockModel.invoke(messages);
            return response;
          },
        });
      } else {
        const openai = new OpenAI({
          organization: process.env.OPEN_AI_ORGANIZATION_ID,
          apiKey: process.env.OPEN_AI_API_KEY,
        });
        serviceAdapter = new OpenAIAdapter({
          openai,
          ...(process.env.OPENAI_MODEL_NAME
            ? { model: process.env.OPENAI_MODEL_NAME }
            : {}),
        });
      }
      
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
