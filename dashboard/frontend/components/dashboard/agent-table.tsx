"use client";

import { useState } from "react";
import { agentTypeLabels } from "@/lib/constants";
import type { Agent, AgentType, AgentStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Brain,
  Bug,
  Fish,
  Zap,
  GitBranch,
  Lock,
  Filter,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const agentIcons: Record<AgentType, typeof Brain> = {
  anomaly: Brain,
  malware: Bug,
  phishing: Fish,
  ddos: Zap,
  mitm: GitBranch,
  ransomware: Lock,
};

const statusConfig: Record<AgentStatus, { label: string; class: string; glow: string }> = {
  active: { label: "Active", class: "bg-success/10 text-success border border-success/20", glow: "neon-glow-green" },
  degraded: { label: "Degraded", class: "bg-warning/10 text-warning border border-warning/20", glow: "" },
  offline: { label: "Offline", class: "bg-destructive/10 text-destructive border border-destructive/20", glow: "neon-glow-red" },
};

export function AgentTable({ agents = [] }: { agents?: Agent[] }) {
  const [typeFilter, setTypeFilter] = useState<AgentType[]>([]);

  const filteredAgents = typeFilter.length > 0
    ? agents.filter((a) => typeFilter.includes(a.type))
    : agents;

  const toggleFilter = (type: AgentType) => {
    setTypeFilter((prev) =>
      prev.includes(type)
        ? prev.filter((t) => t !== type)
        : [...prev, type]
    );
  };

  return (
    <div className="card-3d overflow-hidden">
      <div className="flex items-center justify-between p-5 border-b border-border/50">
        <h3 className="text-sm font-semibold text-card-foreground flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
          Agent Control Panel
        </h3>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="h-8 rounded-lg bg-transparent border-border/50 hover:border-primary/30 hover:bg-primary/5 transition-all duration-300">
              <Filter className="w-4 h-4 mr-2" />
              Filter
              {typeFilter.length > 0 && (
                <span className="ml-2 px-1.5 py-0.5 text-xs rounded-full bg-primary/10 text-primary font-semibold">
                  {typeFilter.length}
                </span>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48 glass-panel rounded-xl">
            {Object.entries(agentTypeLabels).map(([type, label]) => (
              <DropdownMenuCheckboxItem
                key={type}
                checked={typeFilter.includes(type as AgentType)}
                onCheckedChange={() => toggleFilter(type as AgentType)}
                className="rounded-lg"
              >
                {label}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-[11px] text-muted-foreground border-b border-border/50 uppercase tracking-wider">
              <th className="px-5 py-3 font-semibold">Agent</th>
              <th className="px-5 py-3 font-semibold">Type</th>
              <th className="px-5 py-3 font-semibold">Status</th>
              <th className="px-5 py-3 font-semibold">Trust Score</th>
              <th className="px-5 py-3 font-semibold">Accuracy</th>
              <th className="px-5 py-3 font-semibold">Load</th>
              <th className="px-5 py-3 font-semibold">Detections</th>
            </tr>
          </thead>
          <tbody>
            {filteredAgents.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center text-sm text-muted-foreground">
                  No active agents in swarm
                </td>
              </tr>
            ) : (
              filteredAgents.map((agent) => {
                const Icon = agentIcons[agent.type];
                const status = statusConfig[agent.status];

                return (
                  <tr
                    key={agent.id}
                    className="border-b border-border/30 last:border-0 row-hover"
                  >
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary/10 to-neon-purple/10 flex items-center justify-center transition-transform duration-300 hover:scale-110 hover:rotate-3">
                          <Icon className="w-4 h-4 text-primary" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-card-foreground">{agent.name}</p>
                          <p className="text-[11px] text-muted-foreground font-mono">{agent.id}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-sm text-muted-foreground">
                        {agentTypeLabels[agent.type]}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className={cn("px-2.5 py-1 text-[11px] font-semibold rounded-lg badge-glow", status.class)}>
                        {status.label}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className={cn(
                              "h-full rounded-full transition-all duration-500",
                              agent.trustScore >= 90 ? "bg-success" :
                                agent.trustScore >= 70 ? "bg-warning" : "bg-destructive"
                            )}
                            style={{ width: `${agent.trustScore}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium text-card-foreground">{agent.trustScore}%</span>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-sm font-medium text-card-foreground">{agent.detectionAccuracy}%</span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-12 h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className={cn(
                              "h-full rounded-full transition-all duration-500",
                              agent.currentLoad >= 80 ? "bg-destructive" :
                                agent.currentLoad >= 50 ? "bg-warning" : "bg-success"
                            )}
                            style={{ width: `${agent.currentLoad}%` }}
                          />
                        </div>
                        <span className="text-sm text-muted-foreground">{agent.currentLoad}%</span>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-sm font-bold text-primary">{agent.recentDetections}</span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
