"use client";
import { Card } from "@tremor/react";
import CreateOrEditMapping from "./create-or-edit-mapping";
import { useMappings } from "utils/hooks/useMappingRules";
import RulesTable from "./rules-table";
import Loading from "@/app/(keep)/loading";
import { MappingRule } from "./models";
import React, { useEffect, useState } from "react";
import { Button } from "@tremor/react";
import { EmptyStateCard, PageSubtitle, PageTitle } from "@/shared/ui";
import { PlusIcon } from "@heroicons/react/20/solid";
import { Mapping as MappingIcon } from "components/icons";
import { Drawer } from "@/shared/ui/Drawer";
import { useI18n } from "@/i18n/hooks/useI18n";

export default function Mapping() {
  const { t } = useI18n();
  const { data: mappings, isLoading } = useMappings();

  // We use this state to pass the rule that needs to be edited between the CreateNewMapping and the RulesTable Component.
  const [editRule, setEditRule] = useState<MappingRule | null>(null);

  const [isSidePanelOpen, setIsSidePanelOpen] = useState<boolean>(false);

  useEffect(() => {
    if (editRule) {
      setIsSidePanelOpen(true);
    }
  }, [editRule]);

  function handleSidePanelExit(mapping: MappingRule | null) {
    if (mapping) {
      setEditRule(mapping);
    } else {
      setEditRule(null);
      setIsSidePanelOpen(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-row items-center justify-between">
        <div>
          <PageTitle>{t("rules.mapping.title")}</PageTitle>
          <PageSubtitle>
            {t("rules.mapping.description")}
          </PageSubtitle>
        </div>
        <div>
          <Button
            color="orange"
            size="md"
            type="submit"
            onClick={() => setIsSidePanelOpen(true)}
            icon={PlusIcon}
          >
            {t("rules.mapping.addRule")}
          </Button>
        </div>
      </div>
      <Card className="p-0 overflow-hidden">
        <Drawer
          isOpen={isSidePanelOpen}
          onClose={() => handleSidePanelExit(null)}
        >
          <div className="p-4">
            <h2 className="text-lg">{t("rules.mapping.configure")}</h2>
            <p className="text-slate-400">
              {t("rules.mapping.configureDescription")}
            </p>
            <CreateOrEditMapping
              editRuleId={editRule?.id ?? null}
              editCallback={handleSidePanelExit}
            />
          </div>
        </Drawer>

        <div>
          {isLoading ? (
            <Loading />
          ) : mappings && mappings.length > 0 ? (
            <RulesTable
              mappings={mappings}
              editCallback={handleSidePanelExit}
            />
          ) : (
            <EmptyStateCard
              icon={() => <MappingIcon className="!size-8" />}
              title={t("rules.mapping.messages.noRules")}
              description={t("rules.mapping.messages.noRulesDescription")}
            >
              <Button
                color="orange"
                size="md"
                type="submit"
                onClick={() => setIsSidePanelOpen(true)}
                icon={PlusIcon}
              >
                {t("rules.mapping.addRule")}
              </Button>
            </EmptyStateCard>
          )}
        </div>
      </Card>
    </div>
  );
}
