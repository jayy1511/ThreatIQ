"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { isLoggedIn, getToken } from "@/lib/auth"

import { ChartLineInteractive } from "@/components/charts/ChartLineInteractive"
import { ChartBarHorizontal } from "@/components/charts/ChartBarHorizontal"
import { ChartPieLabel } from "@/components/charts/ChartPieLabel"

export default function DashboardPage() {
  const router = useRouter()
  const [history, setHistory] = useState<any[]>([])
  const [pieData, setPieData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isLoggedIn()) {
      router.push("/login")
      return
    }

    const fetchData = async () => {
      try {
        // Fetch history
        const resHistory = await fetch("http://127.0.0.1:8000/analyze/history", {
          headers: {
            Authorization: `Bearer ${getToken()}`,
          },
        })
        if (!resHistory.ok) throw new Error("Failed to fetch history")
        const dataHistory = await resHistory.json()
        setHistory(dataHistory)

        // Fetch judgments (pie chart)
        const resPie = await fetch("http://127.0.0.1:8000/stats/judgments", {
          headers: {
            Authorization: `Bearer ${getToken()}`,
          },
        })
        if (!resPie.ok) throw new Error("Failed to fetch judgments")
        const dataPie = await resPie.json()
        setPieData(dataPie)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [router])

  if (loading) {
    return <div className="p-6">Loading dashboard...</div>
  }

  // ---- Process data for charts ----

  // Line chart: group by day
  const lineData = history.reduce((acc: any[], item) => {
    const date = new Date(item.created_at).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    })
    const existing = acc.find((x) => x.date === date)
    if (existing) {
      existing.count += 1
    } else {
      acc.push({ date, count: 1 })
    }
    return acc
  }, [])

  // Bar chart: group by month
  const barData = history.reduce((acc: any[], item) => {
    const month = new Date(item.created_at).toLocaleString("en-US", {
      month: "long",
    })
    const existing = acc.find((x) => x.month === month)
    if (existing) {
      existing.count += 1
    } else {
      acc.push({ month, count: 1 })
    }
    return acc
  }, [])

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold mb-2">Dashboard</h1>
      <p className="text-muted-foreground mb-6">
        Quick insights into your analysis activity.
      </p>

      {/* Line Chart */}
      <ChartLineInteractive data={lineData} />

      {/* Bar + Pie side by side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ChartBarHorizontal data={barData} />
        <ChartPieLabel data={pieData} />
      </div>
    </div>
  )
}
