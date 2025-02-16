"use server";

import OpenAI from "openai";
import { zodResponseFormat } from "openai/helpers/zod";
import { GENERAL_INSTRUCTIONS } from "../_constants";
import { z } from "zod";
import { V2Step } from "@/entities/workflows/model/types";

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
  stepProperties: V2Step["properties"];
  aim: string;
}) {
  console.log("generateStepDefinition called");
  // Handle condition types (assert and threshold)
  if (stepType === "condition-assert" || stepType === "condition-threshold") {
    const conditionSchema = z.object({
      value: z.string(),
      compare_to: z.string(),
    });
    const response = await openai.beta.chat.completions.parse({
      response_format: zodResponseFormat(
        conditionSchema,
        "condition_properties"
      ),
      model: "gpt-4o",
      messages: [
        {
          role: "system",
          content: GENERAL_INSTRUCTIONS,
        },
        {
          role: "user",
          content: `Generate properties for a ${stepType} condition step named: ${name}. Return a JSON object with "value" and "compare_to" properties to achieve the following: ${aim}.`,
        },
      ],
    });
    return response.choices[0].message.parsed;
  }

  // Handle action and step types
  const combinedParams = [] as string[];
  if ("actionParams" in stepProperties) {
    combinedParams.push(...(stepProperties.actionParams ?? []));
  }
  if ("stepParams" in stepProperties) {
    combinedParams.push(...(stepProperties.stepParams ?? []));
  }

  // Schema for action/step properties
  const withSchema = z.object(
    Object.fromEntries(combinedParams.map((key: string) => [key, z.string()]))
  );

  const propertiesSchema = z.object({
    with: withSchema,
    config: z.string().optional(),
    if: z.string().optional(),
    vars: z.record(z.string(), z.string()).optional(),
  });

  const response = await openai.beta.chat.completions.parse({
    response_format: zodResponseFormat(propertiesSchema, "step_properties"),
    model: "gpt-4o",
    messages: [
      {
        role: "system",
        content: GENERAL_INSTRUCTIONS,
      },
      {
        role: "user",
        content: `Generate properties for the step: ${name} with type: ${stepType}. Return a JSON object that represents the full properties of the step definition to achieve the following: ${aim}. 
        The "with" property can only use these keys: ${combinedParams.map((key) => `"${key}"`).join(", ") ?? "none"}.
        You can optionally include "config", "if", and "vars" properties.`,
      },
    ],
  });
  return response.choices[0].message.parsed;
}
