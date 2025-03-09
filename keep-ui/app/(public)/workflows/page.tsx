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
  "../../examples/workflows/create_jira_ticket_upon_alerts.yml";

export default async function PublicWorkflowsPage() {
  // ... existing code ...
}
