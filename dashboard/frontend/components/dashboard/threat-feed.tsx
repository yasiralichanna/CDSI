"use client";

import { useState } from "react";
import { agentTypeLabels } from "@/lib/constants";
import type { Threat, ThreatSeverity, ThreatStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { AlertTriangle, CheckCircle, Clock, XCircle, ChevronDown, ChevronUp } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

const severityConfig: Record<ThreatSeverity, { label: string; class: string }> = {
  low: { label: "Low", class: "bg-muted text-muted-foreground border border-border" },
  medium: { label: "Medium", class: "bg-warning/10 text-warning border border-warning/20" },
  high: { label: "High", class: "bg-chart-3/10 text-chart-3 border border-chart-3/20" },
  critical: { label: "Critical", class: "bg-destructive/10 text-destructive border border-destructive/20" },
};

const statusConfig: Record<ThreatStatus, { label: string; icon: typeof Clock }> = {
  pending_consensus: { label: "Pending Consensus", icon: Clock },
  confirmed: { label: "Confirmed", icon: AlertTriangle },
  mitigated: { label: "Mitigated", icon: CheckCircle },
  false_positive: { label: "False Positive", icon: XCircle },
};

export function ThreatFeed({ threats = [] }: { threats?: Threat[] }) {
  const [expandedThreat, setExpandedThreat] = useState<string | null>(null);

  return (
    <div className="card-3d overflow-hidden">
      <div className="flex items-center justify-between p-5 border-b border-border/50">
        <h3 className="text-sm font-semibold text-card-foreground flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-destructive animate-pulse" />
          Live Threat Feed
        </h3>
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-destructive opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-destructive" />
          </span>
          <span className="text-[11px] text-destructive font-semibold uppercase tracking-wider">Real-time</span>
        </div>
      </div>
      <div className="divide-y divide-border/30 max-h-96 overflow-y-auto">
        {threats.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            <div className="w-12 h-12 rounded-2xl bg-success/10 flex items-center justify-center mx-auto mb-3">
              <CheckCircle className="w-6 h-6 text-success" />
            </div>
            No threats detected in the last 24 hours
          </div>
        ) : (
          threats.map((threat) => {
            const severity = severityConfig[threat.severity];
            const status = statusConfig[threat.status];
            const StatusIcon = status.icon;
            const isCritical = threat.severity === "critical";

            return (
              <div
                key={threat.id}
                className={cn(
                  "p-4 transition-all duration-300 cursor-pointer",
                  isCritical ? "hover:bg-destructive/[0.03] border-l-2 border-l-destructive/50" : "hover:bg-primary/[0.02]"
                )}
                onClick={() => setExpandedThreat(expandedThreat === threat.id ? null : threat.id)}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-card-foreground font-mono">
                        {threat.id}
                      </span>
                      <span className={cn("px-2 py-0.5 text-[10px] font-bold rounded-lg uppercase tracking-wider badge-glow", severity.class)}>
                        {severity.label}
                      </span>
                      <span className="px-2 py-0.5 text-[10px] font-semibold rounded-lg bg-primary/8 text-primary border border-primary/15">
                        {agentTypeLabels[threat.type]}
                      </span>
                    </div>
                    <p className="mt-1.5 text-sm text-muted-foreground line-clamp-1">
                      {threat.description}
                    </p>
                    <div className="mt-2 flex items-center gap-4 text-[11px] text-muted-foreground">
                      <span>Detected by: <span className="font-medium text-foreground/70">{threat.detectedBy.join(", ")}</span></span>
                      <span>Confidence: <span className="font-bold text-primary">{threat.confidence}%</span></span>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <div className="flex items-center gap-1.5 text-xs">
                      <StatusIcon className={cn(
                        "w-3.5 h-3.5",
                        threat.status === "mitigated" && "text-success",
                        threat.status === "confirmed" && "text-destructive",
                        threat.status === "pending_consensus" && "text-muted-foreground",
                        threat.status === "false_positive" && "text-muted-foreground"
                      )} />
                      <span className={cn(
                        "font-medium",
                        threat.status === "mitigated" && "text-success",
                        threat.status === "confirmed" && "text-destructive",
                        threat.status === "pending_consensus" && "text-muted-foreground",
                        threat.status === "false_positive" && "text-muted-foreground"
                      )}>{status.label}</span>
                    </div>
                    <span className="text-[11px] text-muted-foreground">
                      {formatDistanceToNow(new Date(threat.timestamp), { addSuffix: true })}
                    </span>
                    <div className="mt-2 text-muted-foreground transition-transform duration-200">
                      {expandedThreat === threat.id ? <ChevronUp className="w-4 h-4"/> : <ChevronDown className="w-4 h-4"/>}
                    </div>
                  </div>
                </div>
                
                {expandedThreat === threat.id && threat.metadata?.features && (
                  <div className="mt-4 p-4 rounded-xl bg-muted/50 border border-border/50 text-left cursor-text" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                      <p className="text-[10px] font-bold text-foreground uppercase tracking-[0.15em]">Raw ML Features</p>
                    </div>
                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-1.5 text-xs font-mono">
                      {Object.entries(threat.metadata.features).map(([key, val]) => (
                        <div key={key} className="flex justify-between items-center border-b border-border/30 pb-1">
                          <span className="text-muted-foreground truncate mr-2" title={key}>{key}</span>
                          <span className="text-foreground font-semibold">{String(val)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
