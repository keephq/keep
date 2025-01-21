import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";

export function AlertTimeline() {
  const data = [
    { time: "10m ago", alerts: 8 },
    { time: "8m ago", alerts: 6 },
    { time: "6m ago", alerts: 7 },
    { time: "4m ago", alerts: 4 },
    { time: "2m ago", alerts: 3 },
  ];

  return (
    <div className="h-full w-full">
      <div className="w-full h-64">
        <ResponsiveContainer width="100%" height={250}>
          <BarChart
            data={data}
            margin={{ top: 5, right: 10, left: -30, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Bar
              dataKey="alerts"
              fill="#F97316"
              fillOpacity={0.6}
              barSize={20}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
