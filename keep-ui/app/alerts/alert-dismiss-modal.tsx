import { Button, Title, Subtitle } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
const ReactQuill =
  typeof window === "object" ? require("react-quill") : () => false;
import "react-quill/dist/quill.snow.css";
import Select from 'react-select';


// Assuming AlertDto is already defined elsewhere as in your example
import { AlertDto } from "./models";
import { useState } from "react";
import { getApiURL } from "utils/apiUrl";
import { useSession } from "next-auth/react";
import { format, set } from "date-fns";

interface Props {
  alert: AlertDto | null | undefined;
  handleClose: () => void;
}

export default function AlertDismissModal({ alert, handleClose }: Props) {
    const [dismissComment, setDismissComment] = useState<string>("");
    const [dismissOption, setDismissOption] = useState('');
    // State to track if the date has been set
    const [selectedDate, setSelectedDate] = useState(new Date());
    const [selectedTime, setSelectedTime] = useState(new Date());

    const [isDatePickerOpen, setIsDatePickerOpen] = useState(false);
    // State to track if the date has been set
    const [dateSelected, setDateSelected] = useState(false);
    const [timeSelected, setTimeSelected] = useState(false);

    const [selectedOption, setSelectedOption] = useState({ value: '', label: 'Dismiss Forever' });

  const { data: session } = useSession();
  // if this modal should not be open, do nothing
  if (!alert) return null;

  const isOpen = !!alert;

  const handleDismissOptionChange = (selectedOption: any) => {
    setSelectedOption(selectedOption);
    const custom = selectedOption.value === 'custom';
    setIsDatePickerOpen(custom);
    if(!custom){
      setDateSelected(false);
      setSelectedDate(new Date());
      setTimeSelected(false);
      setSelectedTime(new Date());
    }
  };

  const handleDateChange = (date: any) => {
    const hasTimeChanged = date.getHours() !== selectedTime.getHours() ||
                            date.getMinutes() !== selectedTime.getMinutes() ||
                            date.getSeconds() !== selectedTime.getSeconds();

    const hasDateChanged = date.getDate() !== selectedDate.getDate() ||
                           date.getMonth() !== selectedDate.getMonth() ||
                           date.getFullYear() !== selectedDate.getFullYear();

    setTimeSelected(hasTimeChanged);
    setDateSelected(hasDateChanged);
    // Only update the state if there's a change to reduce unnecessary re-renders
    if (hasTimeChanged || hasDateChanged) {
      // Updating both states together to ensure synchronization
      setSelectedTime(date);
      setSelectedDate(date);

      // Update additional states as required
      setSelectedOption({ value: date.toISOString(), label: `Until ${format(date, "MMMM d, yyyy h:mm:ss aa")}` });
      setDismissOption(date.toISOString());

      // Determine if both date and time have been selected
      const bothSelected = (hasTimeChanged || timeSelected) && (hasDateChanged || dateSelected);
      // Set the state to close the picker if both date and time have been selected
      // This is an optimistic update, assuming the state updates for date and time are synchronous
      if (bothSelected) {
        setIsDatePickerOpen(false);
      }
    }
  };

  const clearAndClose = () => {
    setSelectedOption({ value: 'forever', label: 'Forever' });
    setDateSelected(false);
    setIsDatePickerOpen(false);
    setDismissComment('');
    handleClose();
  };

  const handleDismissChange = async () => {
      const requestData = {
        enrichments: {
            fingerprint: alert.fingerprint,
            dismissed: !alert.dismissed, // Toggle the dismissed state
            note: dismissComment, // use the note mechanism to store the dismiss comment
            dismissUntil: dismissOption,
          },
        fingerprint: alert.fingerprint,
      };
      const response = await fetch(`${getApiURL()}/alerts/enrich`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify(requestData),
      });
      if (response.ok) {
        // Handle success
        console.log("Alert dismissed successfully");
        clearAndClose();
      } else {
        // Handle error
        console.error("Failed to dismiss alert");
        clearAndClose();
      }
    }

  const formats = [
    "header",
    "bold",
    "italic",
    "underline",
    "list",
    "bullet",
    "link",
    "align",
    "blockquote",
    "code-block",
    "color",
  ];

  const modules = {
    toolbar: [
      [{ header: "1" }, { header: "2" }],
      [{ list: "ordered" }, { list: "bullet" }],
      ["bold", "italic", "underline"],
      ["link"],
      [{ align: [] }],
      ["blockquote", "code-block"], // Add quote and code block options to the toolbar
      [{ color: [] }], // Add color option to the toolbar
    ],
  };
  const selectOptions = [
    { value: 'forever', label: 'Dismiss Forever' },
    // Include the 'Choose Date' option only if a custom date has not been selected or the date picker is open
    ...(!dateSelected || isDatePickerOpen ? [{ value: 'custom', label: 'Choose Date' }] : []),
    // Include the selected date option only if a custom date has been selected
    ...(dateSelected && !isDatePickerOpen ? [selectedOption] : []),
  ];

  return (
    <Modal onClose={clearAndClose} isOpen={isOpen} className="overflow-visible">
      {alert && alert.dismissed? (
        <>
        <Subtitle className="text-center">Are you sure you want to restore this alert?</Subtitle>
        <div className="flex justify-center mt-4 space-x-2">
          <Button
            onClick={handleDismissChange}
            color="orange"
          >
            Restore
          </Button>
          <Button
            onClick={clearAndClose}
            variant="secondary"
          >
            Cancel
          </Button>
        </div>
        </>
      ) : (
        <>
          <Title>Dismiss Until</Title>
          <Select
            value={selectedOption}
            onChange={handleDismissOptionChange}
            options={selectOptions}
          />
          {isDatePickerOpen && (
            <div style={{ position: 'absolute', zIndex: 1000 }}>
                <DatePicker
                  selected={selectedDate}
                  onChange={handleDateChange}
                  showTimeSelect
                  timeFormat="p"
                  timeIntervals={15}
                  timeCaption="Time"
                  dateFormat="MMMM d, yyyy h:mm:ss aa"
                  minDate={new Date()}
                  minTime={set(new Date(), { hours: 0, minutes: 0, seconds: 0 })}
                  maxTime={set(new Date(), { hours: 23, minutes: 59, seconds: 59 })}
                  inline
                />
            </div>
            )}
            <Title className="mt-2">Dismiss Comment</Title>
            <ReactQuill
            value={dismissComment}
            onChange={(value: string) => setDismissComment(value)}
            theme="snow"
            placeholder="Add your dismiss comment here..."
            modules={modules}
            formats={formats}
          />
          <Button
              onClick={handleDismissChange}
              color="orange"
              className="mr-2 mt-4"
            >
              Dismiss
            </Button>
            <Button // Use Tremor button for Cancel
              onClick={clearAndClose}
              variant="secondary"
            >
              Cancel
              </Button>
            </>
      )}
    </Modal>
  );
}
