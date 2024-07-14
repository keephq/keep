import { Button, Callout, Icon } from "@tremor/react";
import { getApiURL } from "utils/apiUrl";
import { formatQuery } from "react-querybuilder";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { IoMdClose } from "react-icons/io";
import { FormProvider, SubmitHandler, useForm } from "react-hook-form";
import { CorrelationForm } from "./CorrelationForm";
import { CorrelationGroups } from "./CorrelationGroups";
import { CorrelationSubmission } from "./CorrelationSubmission";
import { useSession } from "next-auth/react";
import { useRules } from "utils/hooks/useRules";
import { CorrelationForm as CorrelationFormType } from ".";
import { useRouter, useSearchParams } from "next/navigation";
import { useSearchAlerts } from "utils/hooks/useSearchAlerts";
import "./CorrelationSidebarBody.css";

export const TIMEFRAME_UNITS = {
  seconds: (amount: number) => amount,
  minutes: (amount: number) => 60 * amount,
  hours: (amount: number) => 3600 * amount,
  days: (amount: number) => 86400 * amount,
} as const;

type CorrelationSidebarBodyProps = {
  toggle: VoidFunction;
  defaultValue: CorrelationFormType;
};

export const CorrelationSidebarBody = ({
  toggle,
  defaultValue,
}: CorrelationSidebarBodyProps) => {
  const apiUrl = getApiURL();

  const methods = useForm<CorrelationFormType>({
    defaultValues: defaultValue,
    mode: "onChange",
  });
  const timeframeInSeconds = TIMEFRAME_UNITS[methods.watch("timeUnit")](
    +methods.watch("timeAmount")
  );

  const { mutate } = useRules();
  const { data: session } = useSession();

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
    const { name, query, description, groupedAttributes } = correlationFormData;

    if (session) {
      const response = await fetch(
        `${apiUrl}/rules${selectedId ? `/${selectedId}` : ""}`,
        {
          method: selectedId ? "PUT" : "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.accessToken}`,
          },
          body: JSON.stringify({
            sqlQuery: formatQuery(query, "parameterized_named"),
            groupDescription: description,
            ruleName: name,
            celQuery: formatQuery(query, "cel"),
            timeframeInSeconds,
            grouping_criteria: alertsFound.length ? groupedAttributes : [],
          }),
        }
      );

      if (response.ok) {
        toggle();
        mutate();
        router.replace("/rules");
      }
    }
  };

  return (
    <div className="space-y-4 pt-10 flex flex-col flex-1">
      {isCalloutShown && (
        <Callout
          className="mb-10 relative"
          title="What is alert correlations? and why grouping alerts together can ease your work"
          color="teal"
        >
          A versatile tool for grouping and consolidating alerts. Read more in
          our{" "}
          <a href="https://docs.keephq.dev/overview/ruleengine" target="_blank">
            docs.
          </a>
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
        <form
          className="flex flex-col justify-between h-full"
          onSubmit={methods.handleSubmit(onCorrelationFormSubmit)}
        >
          <div className="grid grid-cols-2 gap-10 sidebar-form w-full">
            <CorrelationForm alertsFound={alertsFound} isLoading={isLoading} />
            <CorrelationGroups />
          </div>

          <CorrelationSubmission
            toggle={toggle}
            alertsFound={alertsFound}
            timeframeInSeconds={timeframeInSeconds}
          />
        </form>
      </FormProvider>
    </div>
  );
};
