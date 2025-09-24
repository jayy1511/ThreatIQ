"use client"

import { Pie, PieChart } from "recharts"
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

export function ChartPieLabel({ data }: Props) {
  // 🟢 Ensure no "unknown"
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
            <Pie data={cleanedData} dataKey="value" label nameKey="type" />
          </PieChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
