"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Overview } from "@/lib/api";
import { Card, Empty, Skeleton } from "@/components/ui";

export default function AnalyticsPage() {
  const [data, setData] = useState<Overview | null | undefined>(undefined);

  useEffect(() => {
    fetch("/api/proxy/analytics/overview")
      .then((r) => (r.ok ? r.json() : null))
      .then(setData)
      .catch(() => setData(null));
  }, []);

  if (data === undefined)
    return (
      <div className="fade-up space-y-6">
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Analytics
        </h1>
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      </div>
    );
  if (data === null)
    return (
      <Empty title="API unreachable" body="Start the backend and refresh." />
    );

  const classData = Object.entries(data.classification_distribution).map(
    ([name, count]) => ({ name, count }),
  );
  const approvalData = Object.entries(data.approval_rate_by_type).map(
    ([name, stats]) => ({
      name,
      approved: stats.approved,
      rejected: stats.rejected,
    }),
  );

  return (
    <div className="fade-up space-y-6">
      <h1 className="font-display text-xl font-semibold tracking-tight">
        Analytics
      </h1>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="text-sm font-medium">Classification distribution</h2>
          {classData.length === 0 ? (
            <p className="mt-4 text-sm text-ink-dim">No data yet.</p>
          ) : (
            <div className="mt-4 h-64">
              <ResponsiveContainer>
                <BarChart data={classData}>
                  <CartesianGrid stroke="#242a24" vertical={false} />
                  <XAxis
                    dataKey="name"
                    stroke="#5e665e"
                    fontSize={11}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="#5e665e"
                    fontSize={11}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#121512",
                      border: "1px solid #242a24",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    cursor={{ fill: "rgba(182,255,60,0.08)" }}
                  />
                  <Bar dataKey="count" fill="#b6ff3c" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card>
          <h2 className="text-sm font-medium">Approvals vs rejections</h2>
          {approvalData.length === 0 ? (
            <p className="mt-4 text-sm text-ink-dim">
              No reviewed actions yet.
            </p>
          ) : (
            <div className="mt-4 h-64">
              <ResponsiveContainer>
                <BarChart data={approvalData}>
                  <CartesianGrid stroke="#242a24" vertical={false} />
                  <XAxis
                    dataKey="name"
                    stroke="#5e665e"
                    fontSize={11}
                    tickLine={false}
                  />
                  <YAxis
                    stroke="#5e665e"
                    fontSize={11}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#121512",
                      border: "1px solid #242a24",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    cursor={{ fill: "rgba(182,255,60,0.08)" }}
                  />
                  <Bar
                    dataKey="approved"
                    fill="#b6ff3c"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey="rejected"
                    fill="#ff5c5c"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
