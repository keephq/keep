import { Button, Callout, Icon } from "@tremor/react";
import { formatQuery } from "react-querybuilder";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { IoMdClose } from "react-icons/io";
import { FormProvider, SubmitHandler, useForm } from "react-hook-form";
import { CorrelationForm } from "./CorrelationForm";
import { CorrelationGroups } from "./CorrelationGroups";
import { CorrelationSubmission } from "./CorrelationSubmission";
import { Link } from "@/components/ui";
import { ArrowUpRightIcon } from "@heroicons/react/24/outline";
import { useRules } from "utils/hooks/useRules";
import { useRouter, useSearchParams } from "next/navigation";
import { useSearchAlerts } from "utils/hooks/useSearchAlerts";
import { AlertsFoundBadge } from "./AlertsFoundBadge";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useConfig } from "@/utils/hooks/useConfig";
import { showErrorToast } from "@/shared/ui";
import { CorrelationFormType } from "./types";
import { TIMEFRAME_UNITS_TO_SECONDS } from "./timeframe-constants";

type CorrelationSidebarBodyProps = {
  toggle: VoidFunction;
  defaultValue: CorrelationFormType;
};

export const CorrelationSidebarBody = ({
  toggle,
  defaultValue,
}: CorrelationSidebarBodyProps) => {
  const api = useApi();
  const { data: config } = useConfig();

  const methods = useForm<CorrelationFormType>({
    defaultValues: defaultValue,
    mode: "onChange",
  });
  const timeframeInSeconds = methods.watch("timeUnit")
    ? TIMEFRAME_UNITS_TO_SECONDS[methods.watch("timeUnit")](
        +methods.watch("timeAmount")
      )
    : 0;

  const { mutate } = useRules();

  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedId = searchParams ? searchParams.get("id") : null;

  const { data: alertsFound = [], isLoading } = useSearchAlerts({
    query: methods.watch("query"),
    timeframe: timeframeInSeconds,
  });

  const [isCalloutShown, setIsCalloutShown] = useLocalStorage(
    "correlation-callout",
    true
  );

  const onCorrelationFormSubmit: SubmitHandler<CorrelationFormType> = async (
    correlationFormData
  ) => {
    const {
      name,
      query,
      timeUnit,
      description,
      groupedAttributes,
      requireApprove,
      resolveOn,
      createOn,
    } = correlationFormData;

    const body = {
      sqlQuery: formatQuery(query, "parameterized_named"),
      groupDescription: description,
      ruleName: name,
      celQuery: formatQuery(query, "cel"),
      timeframeInSeconds,
      timeUnit: timeUnit,
      groupingCriteria: alertsFound.length ? groupedAttributes : [],
      requireApprove: requireApprove,
      resolveOn: resolveOn,
      createOn: createOn,
    };

    try {
      const response = selectedId
        ? await api.put(`/rules/${selectedId}`, body)
        : await api.post("/rules", body);

      toggle();
      mutate();
      router.replace("/rules");
    } catch (error) {
      showErrorToast(error, "Failed to create correlation rule");
    }
  };

  return (
    <div className="space-y-4 pt-10 flex flex-col flex-1">
      {isCalloutShown && (
        <Callout
          className="relative"
          title="What is alert correlations? and why grouping alerts together can ease your work"
          color="teal"
        >
          A versatile tool for grouping and consolidating alerts. Read more in
          our{"  "}
          <Link
            icon={ArrowUpRightIcon}
            iconPosition="right"
            className="!text-orange-500 hover:!text-orange-700 ml-0.5"
            target="_blank"
            href={`${
              config?.KEEP_DOCS_URL || "https://docs.keephq.dev"
            }/overview/correlation`}
          >
            docs
          </Link>
          <Button
            className="absolute top-0 right-0"
            onClick={() => setIsCalloutShown(false)}
            variant="light"
          >
            <Icon color="gray" icon={IoMdClose} size="sm" />
          </Button>
        </Callout>
      )}
      <FormProvider {...methods}>
        <form onSubmit={methods.handleSubmit(onCorrelationFormSubmit)}>
          <div className="mb-10">
            <CorrelationForm alertsFound={alertsFound} isLoading={isLoading} />
          </div>
          <div className="grid grid-cols-3 gap-x-10 flex-1">
            <CorrelationGroups />

            <div
              className="flex flex-col items-center justify-between gap-5 py-5"
              id="total-results"
            >
              <div className="grow justify-center flex">
                {alertsFound.length > 0 && (
                  <AlertsFoundBadge
                    alertsFound={alertsFound}
                    isLoading={false}
                    vertical={true}
                  />
                )}
              </div>
              <span className="text-xs">
                Rules will be applied only to new alerts. Historical data will
                be ignored
              </span>
              <div className="flex justify-end w-full">
                <CorrelationSubmission
                  toggle={toggle}
                  timeframeInSeconds={timeframeInSeconds}
                />
              </div>
            </div>
          </div>
        </form>
      </FormProvider>
    </div>
  );
};
