"use client"

import { Pie, PieChart, Cell } from "recharts"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

type PieData = { type: string; value: number }

interface Props {
  data: PieData[]
}

const chartConfig = {
  value: {
    label: "Judgments",
  },
} satisfies ChartConfig

// 🎨 Assign fixed colors for each judgment
const COLORS: Record<string, string> = {
  Safe: "#4ade80",      // green
  Phishing: "#f87171",  // red
  Other: "#a3a3a3",     // gray
}

export function ChartPieLabel({ data }: Props) {
  const cleanedData = data.map((d) => ({
    ...d,
    type:
      !d.type || d.type.toLowerCase() === "unknown"
        ? "Other"
        : d.type,
  }))

  return (
    <Card className="flex flex-col">
      <CardHeader className="items-center pb-0">
        <CardTitle>Judgment Breakdown</CardTitle>
        <CardDescription>Safe vs Phishing vs Others</CardDescription>
      </CardHeader>
      <CardContent className="flex-1 pb-0">
        <ChartContainer
          config={chartConfig}
          className="[&_.recharts-pie-label-text]:fill-foreground mx-auto aspect-square max-h-[250px] pb-0"
        >
          <PieChart>
            <ChartTooltip content={<ChartTooltipContent hideLabel />} />
            <Pie
              data={cleanedData}
              dataKey="value"
              label
              nameKey="type"
            >
              {cleanedData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[entry.type] || "#8884d8"}
                />
              ))}
            </Pie>
          </PieChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
