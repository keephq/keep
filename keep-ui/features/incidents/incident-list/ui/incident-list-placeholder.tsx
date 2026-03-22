import { Fragment } from "react";
import { Button, Subtitle, Title } from "@tremor/react";
import { useI18n } from "@/i18n/hooks/useI18n";

interface Props {
  setIsFormOpen: (value: boolean) => void;
}

export const IncidentListPlaceholder = ({ setIsFormOpen }: Props) => {
  const { t } = useI18n();
  const onCreateButtonClick = () => {
    setIsFormOpen(true);
  };

  return (
    <Fragment>
      <div className="flex flex-col items-center justify-center gap-y-8 h-full">
        <div className="text-center space-y-3">
          <Title className="text-2xl">{t("incidents.placeholder.noIncidentsYet")}</Title>
          <Subtitle className="text-gray-400">
            {t("incidents.placeholder.createToEnableAI")}
          </Subtitle>
        </div>
        <Button
          className="mb-10"
          color="orange"
          onClick={() => onCreateButtonClick()}
        >
          {t("incidents.placeholder.createIncident")}
        </Button>
      </div>
    </Fragment>
  );
};
