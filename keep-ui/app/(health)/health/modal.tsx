import { useI18n } from "@/i18n/hooks/useI18n";
import React from "react";
import Modal from "@/components/ui/Modal";
import {
  Badge,
  BarChart,
  Button,
  Card,
  DonutChart,
  Subtitle,
  Title,
} from "@tremor/react";
import { CheckCircle2Icon } from "lucide-react";

interface ProviderHealthResultsModalProps {
  handleClose: () => void;
  isOpen: boolean;
  healthResults: any;
}

const ProviderHealthResultsModal = ({
  handleClose,
  isOpen,
  healthResults,
}: ProviderHealthResultsModalProps) => {
  const { t } = useI18n();
  const handleModalClose = () => {
    handleClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleModalClose}
      title={t("health.resultsTitle")}
      className="w-[50%] max-w-full"
    >
      <div className="relative bg-white p-6 rounded-lg">
        <div className="grid grid-cols-2 cols-2 gap-4">
          <Card className="text-center flex flex-col justify-between">
            <Title>{t("health.spammyAlerts")}</Title>
            {healthResults?.spammy?.length ? (
              <>
                <BarChart
                  className="mx-auto"
                  data={healthResults.spammy}
                  categories={["value"]}
                  index={"date"}
                  xAxisLabel={"Timestamp"}
                  showXAxis={false}
                  colors={["red"]}
                  showAnimation={true}
                  showLegend={false}
                  showGridLines={true}
                />
                {t("health.spammyAlertsDescription")}
              </>
            ) : (
              <>
                <div className="flex justify-center pt-4 pb-2">
                  <CheckCircle2Icon color="green" />
                </div>
                <Subtitle>{t("health.everythingOk")}</Subtitle>
              </>
            )}
          </Card>
          <Card className="text-center flex flex-col justify-between">
            <Title>{t("health.rulesQuality")}</Title>
            {healthResults?.rules?.unused ? (
              <>
                <DonutChart
                  data={[
                    { name: "used", value: healthResults.rules.used },
                    { name: "unused", value: healthResults.rules.unused },
                  ]}
                  showAnimation={true}
                  showLabel={false}
                  colors={["green", "red"]}
                />
                <Subtitle>
                  {t("health.unusedRules", {
                    unused: healthResults?.rules.unused,
                    total: healthResults.rules.used + healthResults.rules.unused
                  })}
                </Subtitle>
              </>
            ) : (
              <>
                <div className="flex justify-center pt-4 pb-2">
                  <CheckCircle2Icon color="green" />
                </div>
                <Subtitle>{t("health.everythingOk")}</Subtitle>
              </>
            )}
          </Card>
          <Card className="text-center flex flex-col justify-between">
            <Title>{t("health.actionable")}</Title>
            <div className="flex justify-center pt-4 pb-2">
              <CheckCircle2Icon color="green" />
            </div>
            <Subtitle>{t("health.everythingOk")}</Subtitle>
          </Card>

          <Card className="text-center flex flex-col justify-between">
            <Title>{t("health.topologyCoverage")}</Title>
            {healthResults?.topology?.uncovered.length ? (
              <>
                <DonutChart
                  data={[
                    {
                      name: "covered",
                      value: healthResults.topology.covered.length,
                    },
                    {
                      name: "uncovered",
                      value: healthResults.topology.uncovered.length,
                    },
                  ]}
                  showAnimation={true}
                  showLabel={false}
                  colors={["green", "red"]}
                />
                <Subtitle>
                  {t("health.notCovered")}
                  {healthResults?.topology?.uncovered.map((service: any) => {
                    return (
                      <Badge key={service.service} className="mr-1">
                        {service.display_name
                          ? service.display_name
                          : service.service}
                      </Badge>
                    );
                  })}
                </Subtitle>
              </>
            ) : (
              <>
                <div className="flex justify-center pt-4 pb-2">
                  <CheckCircle2Icon color="green" />
                </div>
                <Subtitle>{t("health.everythingOk")}</Subtitle>
              </>
            )}
          </Card>
        </div>

        <Title className="text-center pt-10 pb-5">
          {t("health.improveObservability")}
        </Title>
        <Button
          size="lg"
          color="orange"
          variant="primary"
          className="w-full"
          onClick={() => window.open(`https://platform.keephq.dev/providers`)}
        >
          {t("health.signUpToKeep")}
        </Button>
      </div>
    </Modal>
  );
};

export default ProviderHealthResultsModal;
