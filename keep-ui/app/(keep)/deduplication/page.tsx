import { Client } from "./client";

export default function Page() {
  return <Client />;
}

export const metadata = {
  title: "Keep - Deduplication Rules",
  description: "Set up rules to deduplicate similar alerts",
};
