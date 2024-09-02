"use client";
import { Badge, Callout, Card } from "@tremor/react";
import { useMaintenanceRules } from "utils/hooks/useMaintenanceRules";
import Loading from "app/loading";
import { MdWarning } from "react-icons/md";
import { useState } from "react";
import { MaintenanceRule } from "./model";
import CreateOrUpdateMaintenanceRule from "./create-or-update-maintenance-rule";
import MaintenanceRulesTable from "./maintenance-rules-table";

export default function Maintenance() {
  const { data: maintenanceRules, isLoading } = useMaintenanceRules();
  const [maintenanceToEdit, setMaintenanceToEdit] = useState<MaintenanceRule | null>(
    null
  );

  return (
    <Card className="mt-10 p-4 md:p-10 mx-auto">
      <div className="flex divide-x p-2">
        <div className="w-1/2 pr-2.5">
          <CreateOrUpdateMaintenanceRule
            maintenanceToEdit={maintenanceToEdit}
            editCallback={setMaintenanceToEdit}
          />
        </div>
        <div className="w-1/2 pl-2.5">
          {isLoading ? (
            <Loading />
          ) : maintenanceRules && maintenanceRules.length > 0 ? (
            <MaintenanceRulesTable
              maintenanceRules={maintenanceRules}
              editCallback={setMaintenanceToEdit}
            />
          ) : (
            <Callout
              color="orange"
              title="Maintenance rules do not exist"
              icon={MdWarning}
            >
              No maintenance rules found. Configure new maintenance rule using the
              maintenance rules wizard to the left.
            </Callout>
          )}
        </div>
      </div>
    </Card>
  );
}
