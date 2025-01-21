import { AlertDto } from "@/entities/alerts/model";
import { AlertName } from "../AlertName/AlertName";

interface AlertNameAndDescriptionProps {
  alert: AlertDto;
  setNoteModalAlert?: (alert: AlertDto) => void;
  setTicketModalAlert?: (alert: AlertDto) => void;
}

export function AlertNameWithDescription({
  alert,
  setNoteModalAlert,
  setTicketModalAlert,
}: AlertNameAndDescriptionProps) {
  return (
    <div className="flex flex-col gap-1">
      <AlertName
        alert={alert}
        setNoteModalAlert={setNoteModalAlert}
        setTicketModalAlert={setTicketModalAlert}
      />
      <div
        className="text-sm text-gray-500 line-clamp-2 whitespace-pre-wrap"
        title={alert.description}
      >
        {alert.description}
      </div>
    </div>
  );
}
