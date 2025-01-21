import { Fragment } from "react";
import { Button, Subtitle, Title } from "@tremor/react";

interface Props {
  onClearFilters: () => void;
}

export const IncidentsNotFoundPlaceholder = ({ onClearFilters }: Props) => {
  return (
    <Fragment>
      <div className="flex flex-col items-center justify-center gap-y-8 h-full">
        <div className="text-center space-y-3">
          <Title className="text-2xl">No Incidents matching the filter</Title>
          <Subtitle className="text-gray-400">
            Clear filters to see all incidents
          </Subtitle>
        </div>
        <Button
          className="mb-10"
          color="orange"
          onClick={() => onClearFilters()}
        >
          Clear filters
        </Button>
      </div>
    </Fragment>
  );
};
