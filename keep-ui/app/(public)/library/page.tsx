import { Metadata } from "next";
import Link from "next/link";
import { Card } from "@tremor/react";
import { parseWorkflow } from "@/entities/workflows/lib/parser";
import { readFileSync } from "fs";
import path from "path";

export const metadata: Metadata = {
  title: "Public Workflow Templates | Keep",
  description:
    "Discover and use pre-built workflow templates for automation, alerts, and more.",
};

// For POC, we'll just use one template
const TEMPLATE_PATH =
  "../examples/workflows/create_jira_ticket_upon_alerts.yml";

export default async function PublicWorkflowsPage() {
  // Read and parse the template
  const templateContent = readFileSync(
    path.join(process.cwd(), TEMPLATE_PATH),
    "utf8"
  );
  const parsedWorkflow = parseWorkflow(templateContent, []);

  const template = {
    id: "create-jira-ticket-upon-alerts",
    name: "Create Jira Ticket Upon Alerts",
    description:
      parsedWorkflow.properties.description ||
      "Automatically create Jira tickets based on alert conditions",
    rawYaml: templateContent,
    triggers: parsedWorkflow.properties.alert || [],
    actions: parsedWorkflow.sequence || [],
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Workflow Templates</h1>
        <p className="text-gray-600">
          Discover pre-built workflows to automate your processes. Preview and
          import them to your account.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        <Link href={`/library/${template.id}`} className="block">
          <Card className="p-6 flex flex-col justify-between h-full border-2 border-transparent hover:border-orange-400 transition-colors">
            {/* Provider Icons */}
            <div className="flex gap-3 mb-4">
              {template.actions.some((a) =>
                a.type.startsWith("action-jira")
              ) && (
                <span className="p-2 bg-blue-50 rounded-lg">
                  <svg
                    className="w-5 h-5 text-blue-600"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005zm5.723-5.756H5.736a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.762a1.005 1.005 0 0 0-1.001-1.005zM23.017 0H11.459a5.215 5.215 0 0 0 5.214 5.215h2.129v2.057A5.215 5.215 0 0 0 24 12.483V1.005A1.005 1.005 0 0 0 23.017 0z" />
                  </svg>
                </span>
              )}
              {template.actions.some((a) =>
                a.type.startsWith("action-slack")
              ) && (
                <span className="p-2 bg-purple-50 rounded-lg">
                  <svg
                    className="w-5 h-5 text-purple-600"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" />
                  </svg>
                </span>
              )}
            </div>

            {/* Template Info */}
            <div>
              <h3 className="text-lg font-semibold mb-2 line-clamp-2">
                {template.name}
              </h3>
              <p className="text-sm text-gray-600 line-clamp-3">
                {template.description}
              </p>
            </div>

            {/* Trigger Type Badge */}
            <div className="mt-4">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                {Object.keys(template.triggers)[0]?.toUpperCase() || "TRIGGER"}{" "}
                Based
              </span>
            </div>
          </Card>
        </Link>
      </div>
    </div>
  );
}
