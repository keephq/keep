import { FormEvent, useState } from "react";
import { Button, Callout, Icon } from "@tremor/react";
import { getApiURL } from "utils/apiUrl";
import { RuleGroupType, formatQuery } from "react-querybuilder";
import { useLocalStorage } from "utils/hooks/useLocalStorage";
import { IoMdClose } from "react-icons/io";
import { CreateCorrelationForm } from "./CreateCorrelationForm";
import { CreateCorrelationGroups } from "./CreateCorrelationGroups";
import { CreateCorrelationSubmission } from "./CreateCorrelationSubmission";
import { useSession } from "next-auth/react";
import { useRules } from "utils/hooks/useRules";

const TIMEFRAME_UNITS: Record<string, (amount: number) => number> = {
  seconds: (amount) => amount,
  minutes: (amount) => 60 * amount,
  hours: (amount) => 3600 * amount,
  days: (amount) => 86400 * amount,
};

const DEFAULT_QUERY: RuleGroupType = {
  combinator: "and",
  rules: [
    {
      combinator: "and",
      rules: [{ field: "source", operator: "=", value: "" }],
    },
    {
      combinator: "and",
      rules: [{ field: "source", operator: "=", value: "" }],
    },
  ],
};

type CreateCorrelationSidebarBodyProps = {
  toggle: VoidFunction;
};

export const CreateCorrelationSidebarBody = ({
  toggle,
}: CreateCorrelationSidebarBodyProps) => {
  const apiUrl = getApiURL();
  const { mutate } = useRules();
  const { data: session } = useSession();
  const [isCalloutShown, setIsCalloutShown] = useLocalStorage(
    "correlation-callout",
    true
  );

  const [query, setQuery] = useState<RuleGroupType>(DEFAULT_QUERY);

  const onCorrelationFormSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    console.log(Object.fromEntries(new FormData(event.currentTarget)));

    const {
      name,
      description,
      "time-units": timeUnits,
      "time-amount": timeAmount,
      severity,
    } = Object.fromEntries(new FormData(event.currentTarget));

    if (typeof timeUnits !== "string" || typeof timeAmount !== "string") {
      return;
    }

    const timeframeInSeconds = TIMEFRAME_UNITS[timeUnits](+timeAmount);

    if (session) {
      fetch(`${apiUrl}/rules`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.accessToken}`,
        },
        body: JSON.stringify({
          sqlQuery: formatQuery(query, "parameterized_named"),
          ruleName: name,
          celQuery: formatQuery(query, "cel"),
          timeframeInSeconds,
        }),
      })
        .then((response) => response.json())
        .then(() => {
          toggle();
          mutate();
        });
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
      <form
        className="grid grid-cols-2 gap-x-10 flex-1"
        onSubmit={onCorrelationFormSubmit}
      >
        <CreateCorrelationForm />
        <CreateCorrelationGroups query={query} onQueryChange={setQuery} />
        <CreateCorrelationSubmission />
      </form>
    </div>
  );
};
