"use client";
import { Badge, Button, Callout, Card } from "@tremor/react";
import { useMaintenanceRules } from "utils/hooks/useMaintenanceRules";
import Loading from "@/app/(keep)/loading";
import { MdWarning } from "react-icons/md";
import { useState } from "react";
import { MaintenanceRule } from "./model";
import CreateOrUpdateMaintenanceRule from "./create-or-update-maintenance-rule";
import MaintenanceRulesTable from "./maintenance-rules-table";
import { useRouter } from "next/navigation";
import { EmptyStateCard } from "@/shared/ui";
import { FaVolumeMute } from "react-icons/fa";

export default function Maintenance() {
  const { data: maintenanceRules, isLoading } = useMaintenanceRules();
  const [maintenanceToEdit, setMaintenanceToEdit] =
    useState<MaintenanceRule | null>(null);
  const router = useRouter();

  return (
    <Card className="p-2">
      <div className="flex divide-x p-2">
        <div className="w-2/5 pr-2.5">
          <CreateOrUpdateMaintenanceRule
            maintenanceToEdit={maintenanceToEdit}
            editCallback={setMaintenanceToEdit}
          />
        </div>
        <div className="w-3/5 pl-2.5">
          {isLoading ? (
            <Loading />
          ) : maintenanceRules && maintenanceRules.length > 0 ? (
            <MaintenanceRulesTable
              maintenanceRules={maintenanceRules}
              editCallback={(rule) => {
                router.replace(`/maintenance?cel=${rule.cel_query}`);
                setMaintenanceToEdit(rule);
              }}
            />
          ) : (
            <div className="flex justify-center items-center h-full">
              <EmptyStateCard
                noCard
                icon={FaVolumeMute}
                title="No maintenance rules yet"
                description="Create a new maintenance rule using the maintenance rules wizard"
              />
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
