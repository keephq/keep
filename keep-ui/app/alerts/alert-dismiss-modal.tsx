import { useState, useEffect } from "react";
import { Button, Title, Subtitle, Card, Tab, TabGroup, TabList, TabPanel, TabPanels } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import "react-quill/dist/quill.snow.css";
import { AlertDto } from "./models";
import { format, set, isSameDay, isAfter, addMinutes } from "date-fns";
import { getApiURL } from "utils/apiUrl";
import { useSession } from "next-auth/react";
import { usePresets } from "utils/hooks/usePresets";
import { useAlerts } from "utils/hooks/useAlerts";
import { toast } from "react-toastify";
const ReactQuill =
  typeof window === "object" ? require("react-quill") : () => false;
import "./alert-dismiss-modal.css";

interface Props {
  preset: string;
  alert: AlertDto[] | null | undefined;
  handleClose: () => void;
}

export default function AlertDismissModal({
  preset: presetName,
  alert: alerts,
  handleClose,
}: Props) {
  const [dismissComment, setDismissComment] = useState<string>("");
  const [selectedTab, setSelectedTab] = useState<number>(0);
  const [selectedDateTime, setSelectedDateTime] = useState<Date | null>(null);
  const [showError, setShowError] = useState<boolean>(false);

  const { useAllPresets } = usePresets();
  const { mutate: presetsMutator } = useAllPresets();
  const { usePresetAlerts } = useAlerts();
  const { mutate: alertsMutator } = usePresetAlerts(presetName, { revalidateOnMount: false });

  const { data: session } = useSession();

  // Ensuring that the useEffect hook is called consistently
  useEffect(() => {
    const now = new Date();
    const roundedMinutes = Math.ceil(now.getMinutes() / 15) * 15;
    const defaultTime = set(now, { minutes: roundedMinutes, seconds: 0, milliseconds: 0 });
    setSelectedDateTime(defaultTime);
  }, []);

  if (!alerts) return null;

  const isOpen = !!alerts;

  const handleTabChange = (index: number) => {
    setSelectedTab(index);
    if (index === 0) {
      setSelectedDateTime(null);
      setShowError(false);
    }
  };

  const handleDateTimeChange = (date: Date) => {
    setSelectedDateTime(date);
    setShowError(false);
  };

  const handleDismissChange = async () => {
    if (selectedTab === 1 && !selectedDateTime) {
      setShowError(true);
      return;
    }

    const dismissUntil = selectedTab === 0 ? null : selectedDateTime?.toISOString();
    const requests = alerts.map((alert: AlertDto) => {
      const requestData = {
        enrichments: {
          fingerprint: alert.fingerprint,
          dismissed: !alert.dismissed,
          note: dismissComment,
          dismissUntil: dismissUntil || "",
        },
        fingerprint: alert.fingerprint,
      };
      return fetch(`${getApiURL()}/alerts/enrich`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify(requestData),
      });
    });

    const responses = await Promise.all(requests);
    const responsesOk = responses.every((response) => response.ok);
    if (responsesOk) {
      toast.success(`${alerts.length} alerts dismissed successfully!`, {
        position: "top-right",
      });
      await alertsMutator();
      clearAndClose();
    } else {
      clearAndClose();
    }
    await presetsMutator();
  };

  const clearAndClose = () => {
    setSelectedTab(0);
    setSelectedDateTime(null);
    setDismissComment("");
    setShowError(false);
    handleClose();
  };

  const filterPassedTime = (time: Date) => {
    const currentDate = new Date();
    const selectedDate = new Date(time);

    if (isSameDay(currentDate, selectedDate)) {
      return isAfter(selectedDate, currentDate);
    }

    return true;
  };

  return (
    <Modal onClose={clearAndClose} isOpen={isOpen} className="overflow-visible">
      {alerts && alerts.length == 1 && alerts[0].dismissed ? (
        <>
          <Subtitle className="text-center">
            Are you sure you want to restore this alert?
          </Subtitle>
          <div className="flex justify-center mt-4 space-x-2">
            <Button onClick={handleDismissChange} color="orange">
              Restore
            </Button>
          </div>
        </>
      ) : (
        <>
          <TabGroup
            index={selectedTab}
            onIndexChange={(index: number) => handleTabChange(index)}
          >
            <TabList>
              <Tab>Dismiss Forever</Tab>
              <Tab>Dismiss Until</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <Title>Dismiss Comment</Title>
                <ReactQuill
                  value={dismissComment}
                  onChange={(value: string) => setDismissComment(value)}
                  theme="snow"
                  placeholder="Add your dismiss comment here..."
                />
              </TabPanel>
              <TabPanel>
                <Card className="relative z-50 mt-4 flex justify-center items-center">
                  <div className="flex flex-col items-center">
                    <DatePicker
                      selected={selectedDateTime}
                      onChange={handleDateTimeChange}
                      showTimeSelect
                      timeFormat="p"
                      timeIntervals={15}
                      timeCaption="Time"
                      dateFormat="MMMM d, yyyy h:mm:ss aa"
                      minDate={new Date()}
                      minTime={set(new Date(), {
                        hours: 0,
                        minutes: 0,
                        seconds: 0,
                      })}
                      maxTime={set(new Date(), {
                        hours: 23,
                        minutes: 59,
                        seconds: 59,
                      })}
                      filterTime={filterPassedTime}
                      inline
                      calendarClassName="custom-datepicker"

                    />
                    {showError && <div className="text-red-500 mt-2">Must choose a date</div>}
                  </div>
                </Card>
                <Title className="mt-2">Dismiss Comment</Title>
                <ReactQuill
                  value={dismissComment}
                  onChange={(value: string) => setDismissComment(value)}
                  theme="snow"
                  placeholder="Add your dismiss comment here..."
                />
              </TabPanel>
            </TabPanels>
          </TabGroup>
          <div className="mt-4 flex justify-end space-x-2">
            <Button onClick={handleDismissChange} color="orange">
              Dismiss
            </Button>
          </div>
        </>
      )}
    </Modal>
  );
}
