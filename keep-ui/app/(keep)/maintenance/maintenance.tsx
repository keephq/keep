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
import { useI18n } from "@/i18n/hooks/useI18n";

export default function Maintenance() {
  const { data: maintenanceRules, isLoading } = useMaintenanceRules();
  const [maintenanceToEdit, setMaintenanceToEdit] =
    useState<MaintenanceRule | null>(null);
  const router = useRouter();
  const { t } = useI18n();

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
                title={t("maintenance.messages.noRules")}
                description={t("maintenance.messages.noRulesDescription")}
              />
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
