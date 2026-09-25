"use client";

import { useState } from "react";
import { useSwarmData } from "@/hooks/use-swarm-data";
import { agentTypeLabels } from "@/lib/constants";
import type { AgentType } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Brain,
  Bug,
  Fish,
  Zap,
  GitBranch,
  Lock,
  TrendingUp,
  Shield,
  Target,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const attackTypes: { type: AgentType; icon: typeof Brain }[] = [
  { type: "ddos", icon: Zap },
  { type: "malware", icon: Bug },
  { type: "phishing", icon: Fish },
  { type: "mitm", icon: GitBranch },
  { type: "ransomware", icon: Lock },
  { type: "anomaly", icon: Brain },
];

// Generate mock trend data for styling purposes since we don't store 24h timeseries on backend yet
const generateTrendData = (type: AgentType) => {
  const now = new Date();
  return Array.from({ length: 24 }, (_, i) => {
    const hour = new Date(now.getTime() - (23 - i) * 60 * 60 * 1000);
    return {
      time: `${hour.getHours().toString().padStart(2, "0")}:00`,
      detections: Math.floor(Math.random() * 20 + 5),
      mitigated: Math.floor(Math.random() * 18 + 3),
    };
  });
};

export function AttackTabs() {
  const { attackStats, threats } = useSwarmData();
  const [activeType, setActiveType] = useState<AgentType>("ddos");
  const stats = attackStats?.[activeType] || { detected: 0, mitigated: 0, accuracy: 0.0 };
  const trendData = generateTrendData(activeType);
  const typeThreats = threats?.filter((t) => t.type === activeType) || [];

  return (
    <div className="card-3d overflow-hidden">
      <div className="border-b border-border/50">
        <div className="flex overflow-x-auto">
          {attackTypes.map(({ type, icon: Icon }) => (
            <button
              key={type}
              onClick={() => setActiveType(type)}
              className={cn(
                "flex items-center gap-2 px-5 py-3.5 text-sm font-semibold whitespace-nowrap border-b-2 transition-all duration-300",
                activeType === type
                  ? "border-primary text-primary bg-primary/[0.04]"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/50"
              )}
            >
              <Icon className={cn("w-4 h-4 transition-transform duration-300", activeType === type && "scale-110")} />
              {agentTypeLabels[type].replace(" Detection", "")}
            </button>
          ))}
        </div>
      </div>

      <div className="p-5">
        {/* Stats Row */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="p-4 rounded-xl bg-muted/30 border border-border/30 transition-all duration-300 hover:bg-destructive/[0.03] hover:border-destructive/15 group">
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-destructive transition-transform duration-300 group-hover:scale-110" />
              <span className="text-[11px] text-muted-foreground font-semibold uppercase tracking-wider">Detected</span>
            </div>
            <p className="text-2xl font-bold text-card-foreground">{stats.detected}</p>
          </div>
          <div className="p-4 rounded-xl bg-muted/30 border border-border/30 transition-all duration-300 hover:bg-success/[0.03] hover:border-success/15 group">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="w-4 h-4 text-success transition-transform duration-300 group-hover:scale-110" />
              <span className="text-[11px] text-muted-foreground font-semibold uppercase tracking-wider">Mitigated</span>
            </div>
            <p className="text-2xl font-bold text-success">{stats.mitigated}</p>
          </div>
          <div className="p-4 rounded-xl bg-muted/30 border border-border/30 transition-all duration-300 hover:bg-primary/[0.03] hover:border-primary/15 group">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-primary transition-transform duration-300 group-hover:scale-110" />
              <span className="text-[11px] text-muted-foreground font-semibold uppercase tracking-wider">Accuracy</span>
            </div>
            <p className="text-2xl font-bold text-card-foreground">{stats.accuracy}%</p>
          </div>
        </div>

        {/* Trend Chart */}
        <div className="mb-6">
          <p className="text-[10px] text-muted-foreground mb-3 uppercase tracking-[0.15em] font-bold">24-Hour Detection Trend</p>
          <div className="h-48 rounded-xl bg-muted/20 p-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="detectionGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="mitigatedGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#16a34a" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis 
                  dataKey="time" 
                  stroke="#94a3b8" 
                  fontSize={10}
                  tickLine={false}
                  interval={5}
                />
                <YAxis 
                  stroke="#94a3b8" 
                  fontSize={10}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "rgba(255, 255, 255, 0.95)",
                    border: "1px solid rgba(14, 165, 233, 0.15)",
                    borderRadius: "12px",
                    fontSize: "12px",
                    boxShadow: "0 8px 30px rgba(14, 165, 233, 0.1)",
                    backdropFilter: "blur(12px)",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="detections"
                  stroke="#0ea5e9"
                  strokeWidth={2.5}
                  fill="url(#detectionGradient)"
                  name="Detections"
                />
                <Area
                  type="monotone"
                  dataKey="mitigated"
                  stroke="#16a34a"
                  strokeWidth={2.5}
                  fill="url(#mitigatedGradient)"
                  name="Mitigated"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Alerts */}
        <div>
          <p className="text-[10px] text-muted-foreground mb-3 uppercase tracking-[0.15em] font-bold">Recent Alerts</p>
          {typeThreats.length > 0 ? (
            <div className="space-y-2">
              {typeThreats.slice(0, 3).map((threat) => (
                <div
                  key={threat.id}
                  className="flex items-center justify-between p-4 rounded-xl bg-muted/30 border border-border/30 hover:bg-primary/[0.03] hover:border-primary/15 transition-all duration-300 group"
                >
                  <div>
                    <p className="text-sm font-semibold text-card-foreground group-hover:text-primary transition-colors">{threat.id}</p>
                    <p className="text-[11px] text-muted-foreground line-clamp-1">{threat.description}</p>
                  </div>
                  <span className={cn(
                    "px-2.5 py-1 text-[10px] font-bold rounded-lg border uppercase tracking-wider badge-glow",
                    threat.severity === "critical" && "bg-destructive/10 text-destructive border-destructive/20",
                    threat.severity === "high" && "bg-chart-3/10 text-chart-3 border-chart-3/20",
                    threat.severity === "medium" && "bg-warning/10 text-warning border-warning/20",
                    threat.severity === "low" && "bg-muted text-muted-foreground border-border"
                  )}>
                    {threat.severity}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-8">
              No recent alerts for this attack type
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
