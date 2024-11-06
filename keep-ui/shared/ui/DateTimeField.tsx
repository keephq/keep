import TimeAgo from "react-timeago";
import { format } from "date-fns";

export const DateTimeField = ({ date }: { date: Date }) => {
  const formatString = "dd MMM yy, HH:mm.ss 'UTC'";
  return (
    <div>
      <p className="">
        <TimeAgo date={date + "Z"} />
      </p>
      <p className="text-gray-500 text-xs">
        {format(new Date(date), formatString)}
      </p>
    </div>
  );
};
