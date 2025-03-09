import { Metadata } from "next";
import { redirect } from "next/navigation";
import { readFileSync } from "fs";
import path from "path";
import { parseWorkflow } from "@/entities/workflows/lib/parser";
import { PublicWorkflowBuilder } from "./ui/PublicWorkflowBuilder";
import { Button } from "@tremor/react";
import { ImportButton } from "./ui/ImportButton";

// For POC, we only generate one static path
export async function generateStaticParams() {
  return [{ workflowId: "create-jira-ticket-upon-alerts" }];
}

// Dynamic metadata for SEO
export async function generateMetadata({
  params,
}: {
  params: { workflowId: string };
}): Promise<Metadata> {
  if (params.workflowId !== "create-jira-ticket-upon-alerts") {
    return { title: "Workflow Not Found" };
  }

  return {
    title: "Create Jira Ticket Upon Alerts | Keep Workflow Template",
    description: "Automatically create Jira tickets based on alert conditions",
    openGraph: {
      title: "Create Jira Ticket Upon Alerts | Keep Workflow Template",
      description:
        "Automatically create Jira tickets based on alert conditions",
      type: "website",
    },
  };
}

export default async function WorkflowTemplatePage({
  params,
}: {
  params: { workflowId: string };
}) {
  if (params.workflowId !== "create-jira-ticket-upon-alerts") {
    redirect("/workflows");
  }

  const templatePath = path.join(
    process.cwd(),
    "../examples/workflows/create_jira_ticket_upon_alerts.yml"
  );
  const templateContent = readFileSync(templatePath, "utf8");
  const parsedWorkflow = parseWorkflow(templateContent, []);

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header Section */}
      <div className="mb-8">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h1 className="text-3xl font-bold mb-2">
              Create Jira Ticket Upon Alerts
            </h1>
            <p className="text-gray-600">
              {parsedWorkflow.properties.description}
            </p>
          </div>
          <ImportButton workflowId={params.workflowId} />
        </div>

        {/* Feature Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="font-semibold text-gray-900">Trigger Type</h3>
            <p className="text-sm text-gray-600 mt-1">Alert-based workflow</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="font-semibold text-gray-900">Integrations</h3>
            <p className="text-sm text-gray-600 mt-1">Jira, Slack</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="font-semibold text-gray-900">Use Case</h3>
            <p className="text-sm text-gray-600 mt-1">Incident Management</p>
          </div>
        </div>
      </div>

      {/* Workflow Builder */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="h-[calc(100vh-350px)]">
          <PublicWorkflowBuilder workflowRaw={templateContent} />
        </div>
      </div>

      {/* Structured Data for SEO */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            name: "Create Jira Ticket Upon Alerts",
            description: parsedWorkflow.properties.description,
            applicationCategory: "Workflow Automation",
            operatingSystem: "Any",
            offers: {
              "@type": "Offer",
              price: "0",
              priceCurrency: "USD",
            },
          }),
        }}
      />
    </div>
  );
}
