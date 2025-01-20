import TimeAgo from "react-timeago";
import { format } from "date-fns";

interface DateTimeFieldProps {
  date: Date;
  showRelative?: boolean;
  className?: string;
}

export const DateTimeField = ({
  date,
  showRelative = true,
  className,
}: DateTimeFieldProps) => {
  const formatString = "dd MMM yy, HH:mm.ss 'UTC'";
  const textColorClass =
    className?.match(/text-gray-\d+/)?.[0] || "text-gray-500";

  return (
    <div className={className}>
      {showRelative && (
        <p className={textColorClass}>
          <TimeAgo date={date + "Z"} />
        </p>
      )}
      <p className={`${textColorClass} text-xs`}>
        {format(new Date(date), formatString)}
      </p>
    </div>
  );
};
