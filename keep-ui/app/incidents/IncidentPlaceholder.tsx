import { Fragment, useEffect } from "react";
import { Button, Subtitle, Title } from "@tremor/react";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { toast } from "react-toastify";

interface Props {
  setIsFormOpen: (value: boolean) => void;
}

const FirstTimeToast = () => {
  const openDocs = (link: string) => {
    window.open(link, "_blank");
  };

  return (
    <div className="flex flex-col gap-y-4 items-center">
      If this is the first time you have logged in to Keep, we suggest reading
      some of our docs 📚
      <div className="flex gap-x-4">
        <div className="flex flex-col">
          See our supported providers
          <Button
            size="xs"
            variant="secondary"
            onClick={() =>
              openDocs("https://docs.keephq.dev/providers/overview")
            }
          >
            Providers
          </Button>
        </div>
        <div className="flex flex-col">
          Read an introduction
          <Button
            size="xs"
            variant="secondary"
            onClick={() =>
              openDocs("https://docs.keephq.dev/overview/introduction")
            }
          >
            Introduction
          </Button>
        </div>
        <div className="flex flex-col">
          See some classic use cases
          <Button
            size="xs"
            variant="secondary"
            onClick={() =>
              openDocs("https://docs.keephq.dev/overview/usecases")
            }
          >
            Use Cases
          </Button>
        </div>
      </div>
    </div>
  );
};

export const IncidentPlaceholder = ({ setIsFormOpen }: Props) => {
  useEffect(() => {
    const firstTimeToastShown = localStorage.getItem("firstTimeToastShown");
    if (!firstTimeToastShown) {
      toast(<FirstTimeToast />, {
        type: "info",
        icon: false,
        position: toast.POSITION.TOP_CENTER,
        autoClose: 10000,
        className: "w-[1000px]",
        progressStyle: { backgroundColor: "orange" },
      });
      localStorage.setItem("firstTimeToastShown", "true");
    }
  }, []);

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
