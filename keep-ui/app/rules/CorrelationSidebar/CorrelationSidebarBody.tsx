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

const TIMEFRAME_UNITS: Record<string, (amount: number) => number> = {
  seconds: (amount) => amount,
  minutes: (amount) => 60 * amount,
  hours: (amount) => 3600 * amount,
  days: (amount) => 86400 * amount,
};

type CorrelationSidebarBodyProps = {
  toggle: VoidFunction;
  defaultValue: CorrelationFormType;
};

export const CorrelationSidebarBody = ({
  toggle,
  defaultValue,
}: CorrelationSidebarBodyProps) => {
  const apiUrl = getApiURL();

  const { mutate } = useRules();
  const { data: session } = useSession();

  const router = useRouter();
  const searchParams = useSearchParams();
  const selectedId = searchParams ? searchParams.get("id") : null;

  const [isCalloutShown, setIsCalloutShown] = useLocalStorage(
    "correlation-callout",
    true
  );

  const methods = useForm<CorrelationFormType>({ defaultValues: defaultValue });

  const onCorrelationFormSubmit: SubmitHandler<CorrelationFormType> = async (
    correlationFormData
  ) => {
    const {
      name,
      query,
      description,
      timeUnit,
      timeAmount,
      groupedAttributes,
    } = correlationFormData;

    const timeframeInSeconds = TIMEFRAME_UNITS[timeUnit](+timeAmount);

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
            ruleName: name,
            celQuery: formatQuery(query, "cel"),
            timeframeInSeconds,
            grouping_criteria: groupedAttributes,
            item_description: description,
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
          Rapidiously aggregate parallel initiatives before client-focused
          action items, Distinctively extend effective convergence with
          ubiquitous deliverables. Rapidiously productize long-term high-impact
          infomediaries through multifunctional &quot;outside the box&quot;
          thinking. Assertively communicate business testing procedures before
          accurate deliverables. Uniquely maintain accurate architectures
          through functional benefits.
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
          className="grid grid-cols-2 gap-x-10 flex-1"
          onSubmit={methods.handleSubmit(onCorrelationFormSubmit)}
        >
          <CorrelationForm />
          <CorrelationGroups />
          <CorrelationSubmission toggle={toggle} />
        </form>
      </FormProvider>
    </div>
  );
};
