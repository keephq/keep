import { useState, useEffect } from "react";
import {
  Button,
  Title,
  Subtitle,
  Card,
  Tab,
  TabGroup,
  TabList,
  TabPanel,
  TabPanels,
} from "@tremor/react";
import Modal from "@/components/ui/Modal";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { AlertDto } from "@/entities/alerts/model";
import { set, isSameDay, isAfter } from "date-fns";
import { useAlerts } from "@/entities/alerts/model/useAlerts";
import { toast } from "react-toastify";
import "react-quill-new/dist/quill.snow.css";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";
import "./alert-dismiss-modal.css";
import dynamic from "next/dynamic";

const ReactQuill = dynamic(() => import("react-quill-new"), { ssr: false });

interface Props {
  preset: string;
  alert: AlertDto[] | null | undefined;
  handleClose: () => void;
}

export function AlertDismissModal({
  preset: presetName,
  alert: alerts,
  handleClose,
}: Props) {
  const [dismissComment, setDismissComment] = useState<string>("");
  const [selectedTab, setSelectedTab] = useState<number>(0);
  const [selectedDateTime, setSelectedDateTime] = useState<Date | null>(null);
  const [showError, setShowError] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const revalidateMultiple = useRevalidateMultiple();
  const presetsMutator = () => revalidateMultiple(["/preset"]);
  const { alertsMutator } = useAlerts();

  const api = useApi();
  // Ensuring that the useEffect hook is called consistently
  useEffect(() => {
    const now = new Date();
    const roundedMinutes = Math.ceil(now.getMinutes() / 15) * 15;
    const defaultTime = set(now, {
      minutes: roundedMinutes,
      seconds: 0,
      milliseconds: 0,
    });
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

    setIsLoading(true);

    const dismissUntil =
      selectedTab === 0 ? null : selectedDateTime?.toISOString();

    const requestData = {
      enrichments: {
        dismissed: !alerts[0]?.dismissed,
        note: dismissComment,
        dismissUntil: dismissUntil || "",
      },
      fingerprints: alerts.map((alert: AlertDto) => alert.fingerprint),
    };

    try {
      await api.post(`/alerts/batch_enrich`, requestData);
      toast.success(`${alerts.length} alerts dismissed successfully!`, {
        position: "top-right",
      });
      await alertsMutator();
      await presetsMutator();
    } catch (error) {
      showErrorToast(error, "Failed to dismiss alerts");
    } finally {
      clearAndClose();
      setIsLoading(false);
    }
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
    <Modal
      onClose={clearAndClose}
      isOpen={isOpen}
      className="overflow-visible"
      beforeTitle={alerts?.[0]?.name}
      title="Dismiss Alert"
    >
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
            className="mb-4"
          >
            <TabList>
              <Tab>Dismiss Forever</Tab>
              <Tab>Dismiss Until</Tab>
            </TabList>
            <TabPanels>
              <TabPanel></TabPanel>
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
                    {showError && (
                      <div className="text-red-500 mt-2">
                        Must choose a date
                      </div>
                    )}
                  </div>
                </Card>
              </TabPanel>
            </TabPanels>
          </TabGroup>
          <Title>Dismiss Comment</Title>
          <div className="mt-4 border border-gray-200 rounded-lg overflow-hidden">
            <ReactQuill
              value={dismissComment}
              onChange={(value: string) => setDismissComment(value)}
              theme="snow"
              placeholder="Add your dismiss comment here..."
            />
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="secondary" color="orange" onClick={clearAndClose}>
              Cancel
            </Button>
            <Button
              onClick={handleDismissChange}
              color="orange"
              loading={isLoading}
            >
              Dismiss
            </Button>
          </div>
        </>
      )}
    </Modal>
  );
}
