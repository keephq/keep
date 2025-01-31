import { Fragment } from "react";
import { Button, Subtitle, Title } from "@tremor/react";

interface Props {
  setIsFormOpen: (value: boolean) => void;
}

export const IncidentListPlaceholder = ({ setIsFormOpen }: Props) => {
  const onCreateButtonClick = () => {
    setIsFormOpen(true);
  };

  return (
    <Fragment>
      <div className="flex flex-col items-center justify-center gap-y-8 h-full">
        <div className="text-center space-y-3">
          <Title className="text-2xl">No Incidents Yet</Title>
          <Subtitle className="text-gray-400">
            Create incidents manually to enable AI detection
          </Subtitle>
        </div>
        <Button
          className="mb-10"
          color="orange"
          onClick={() => onCreateButtonClick()}
        >
          Create Incident
        </Button>
      </div>
    </Fragment>
  );
};
