"use server";

import OpenAI from "openai";
import { V2Properties } from "../types";
import { zodResponseFormat } from "openai/helpers/zod";
import { GENERAL_INSTRUCTIONS } from "../_constants";
import { z } from "zod";

// TEMPORARY
// TODO: Remove this
const openai = new OpenAI({
  organization: process.env.OPEN_AI_ORGANIZATION_ID,
  apiKey: process.env.OPEN_AI_API_KEY,
});

export async function generateStepDefinition({
  name,
  stepType,
  stepProperties,
  aim,
}: {
  name: string;
  stepType: string;
  stepProperties: V2Properties;
  aim: string;
}) {
  const combinedParams = [
    ...(stepProperties?.actionParams ?? []),
    ...(stepProperties?.stepParams ?? []),
  ];
  const zodSchema = z
    .object(
      Object.fromEntries(combinedParams.map((key: string) => [key, z.string()]))
    )
    .partial()
    .strict();
  const response = await openai.beta.chat.completions.parse({
    response_format: zodResponseFormat(
      zodSchema,
      "step_definition_properties_with"
    ),
    model: "gpt-4o",
    messages: [
      {
        role: "system",
        content: GENERAL_INSTRUCTIONS,
      },
      {
        role: "user",
        content: `Generate a step definition for the step: ${name} with type: ${stepType}. Return a JSON object that represents "with" property of the step definition with properties to achieve the following: ${aim}. Allowed keys are: ${combinedParams.map((key) => `"${key}"`).join(", ") ?? "none"}`,
      },
    ],
  });
  return response.choices[0].message.parsed;
}
