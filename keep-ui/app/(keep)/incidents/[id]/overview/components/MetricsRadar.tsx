import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";

export function MetricsRadar() {
  const data = [
    { subject: "Providers", value: 80 },
    { subject: "Quality", value: 90 },
    { subject: "Noise", value: 70 },
    { subject: "Topology", value: 85 },
    { subject: "Corr.", value: 75 },
  ];

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart
          cx="50%"
          cy="50%"
          outerRadius="75%"
          data={data}
          margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
        >
          <PolarGrid gridType="polygon" stroke="#444" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fill: "#666", fontSize: 14 }}
            axisLine={{ stroke: "#444" }}
          />
          <PolarRadiusAxis
            tick={{ fill: "#666" }}
            axisLine={{ stroke: "#444" }}
            stroke="#444"
            tickCount={6}
          />
          <Radar
            name="Metrics"
            dataKey="value"
            stroke="#F97316"
            fill="#F97316"
            fillOpacity={0.6}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
