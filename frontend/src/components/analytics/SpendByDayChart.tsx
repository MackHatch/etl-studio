"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

type ByDayPoint = { date: string; spend: number };

export function SpendByDayChart({ data }: { data: ByDayPoint[] }) {
  return (
    <div className="h-64 w-full" data-testid="analytics-chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12 }}
            tickFormatter={(v) => (v ? new Date(v).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "")}
          />
          <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${v}`} />
          <Tooltip
            formatter={(value: number) => [`$${value.toLocaleString()}`, "Spend"]}
            labelFormatter={(label) => (label ? new Date(label).toLocaleDateString() : "")}
          />
          <Line
            type="monotone"
            dataKey="spend"
            stroke="#2563eb"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
