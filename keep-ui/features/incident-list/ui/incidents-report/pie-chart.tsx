import { DonutChart } from "@tremor/react";
import { useMemo } from "react";

interface PieChartProps {
  data: { name: string; value: number }[];
  formatCount?: (value: number) => string;
}

export const PieChart: React.FC<PieChartProps> = ({
  data,
  formatCount: counterFormatter,
}) => {
  const sortedByValue = useMemo(() => {
    return [...data].sort((a, b) => b.value - a.value);
  }, [data]);

  const colors = useMemo(
    () => [
      "red-500",
      "blue-700",
      "green-500",
      "orange-500",
      "yellow-500",
      "purple-500",
      "teal-500",
      "cyan-500",
      "rose-500",
      "lime-500",
    ],
    []
  );

  return (
    <div className="flex items-center gap-10">
      <DonutChart
        className="w-48 h-48"
        data={sortedByValue}
        colors={colors}
        variant="pie"
        onValueChange={(v) => console.log(v)}
      />
      <div className="flex-col">
        {sortedByValue.map((chartValue, index) => (
          <div key={chartValue.name} className="flex gap-2">
            <div className={`min-w-5 h-3 mt-2 bg-${colors[index]}`}></div>
            <div>
              <span className="font-bold">{chartValue.name}</span> -{" "}
              {counterFormatter && (
                <span>{counterFormatter(chartValue.value)}</span>
              )}
              {!counterFormatter && <span>{chartValue.value}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
