import { useI18n } from "@/i18n/hooks/useI18n";
import { Button, Icon, Subtitle, Title, Text } from "@tremor/react";
import { Dialog } from "@headlessui/react";
import { IoMdClose } from "react-icons/io";
import { useSearchParams } from "next/navigation";

type CorrelationSidebarHeaderProps = {
  toggle: VoidFunction;
};

export const CorrelationSidebarHeader = ({
  toggle,
}: CorrelationSidebarHeaderProps) => {
  const { t } = useI18n();
  const searchParams = useSearchParams();
  const isRuleBeingEdited = searchParams ? searchParams.get("id") : null;

  return (
    <div className="flex justify-between p-4">
      <div>
        <Title className="font-bold">
          {isRuleBeingEdited ? t("common.actions.edit") : t("common.actions.create")} {t("rules.correlation.title")}
        </Title>
        <Text>{t("rules.correlation.sidebar.groupDescription")}</Text>
      </div>
      <div>
        <Button onClick={toggle} variant="light">
          <Icon color="gray" icon={IoMdClose} size="xl" />
        </Button>
      </div>
    </div>
  );
};
