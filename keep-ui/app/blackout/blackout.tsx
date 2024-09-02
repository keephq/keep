"use client";
import { Badge, Callout, Card } from "@tremor/react";
import { useBlackouts } from "utils/hooks/useBlackoutRules";
import Loading from "app/loading";
import { MdWarning } from "react-icons/md";
import { useState } from "react";
import { BlackoutRule } from "./model";
import CreateOrUpdateBlackoutRule from "./create-or-update-blackout-rule";
import BlackoutsTable from "./blackout-table";

export default function Blackout() {
  const { data: blackouts, isLoading } = useBlackouts();
  const [blackoutToEdit, setBlackoutToEdit] = useState<BlackoutRule | null>(
    null
  );

  return (
    <Card className="mt-10 p-4 md:p-10 mx-auto">
      <div className="flex divide-x p-2">
        <div className="w-1/3 pr-2.5">
          <CreateOrUpdateBlackoutRule
            blackoutToEdit={blackoutToEdit}
            editCallback={setBlackoutToEdit}
          />
        </div>
        <div className="w-2/3 pl-2.5">
          {isLoading ? (
            <Loading />
          ) : blackouts && blackouts.length > 0 ? (
            <BlackoutsTable
              blackouts={blackouts}
              editCallback={setBlackoutToEdit}
            />
          ) : (
            <Callout
              color="orange"
              title="Blackout rules do not exist"
              icon={MdWarning}
            >
              No blackout rules found. Configure new blackout rule using the
              blackout rules wizard to the left.
            </Callout>
          )}
        </div>
      </div>
    </Card>
  );
}