import { SupersetDashboard } from "./SupersetDashboard";

// Metadata can be imported in a separate layout.tsx file
export const metadata = {
  title: "Analytics Dashboard",
  description: "Analytics dashboard powered by Apache Superset",
};

export default function DashboardPage() {
  return (
    <div className="relative w-full">
      {/* The SupersetDashboard component is already handling its own loading and error states */}
      <SupersetDashboard />
    </div>
  );
}
