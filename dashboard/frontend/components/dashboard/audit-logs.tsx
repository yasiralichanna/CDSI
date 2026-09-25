"use client";

import { useSwarmData } from "@/hooks/use-swarm-data";
import { FileText, ChevronDown, ChevronUp, Brain } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useState } from "react";
import { cn } from "@/lib/utils";

export function AuditLogs() {
  const { logs } = useSwarmData();
  const [expandedLog, setExpandedLog] = useState<string | null>(null);
  const auditLogs = logs || [];

  return (
    <div className="card-3d overflow-hidden">
      <div className="flex items-center justify-between p-5 border-b border-border/50">
        <h3 className="text-sm font-semibold text-card-foreground flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-neon-cyan animate-pulse" />
          Audit Logs & AI Reasoning
        </h3>
        <span className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-primary/8 text-primary border border-primary/15">
          {auditLogs.length} entries
        </span>
      </div>
      <div className="divide-y divide-border/30 max-h-96 overflow-y-auto">
        {auditLogs.map((log) => (
          <div key={log.id} className="transition-all duration-300 hover:bg-primary/[0.02]">
            <button
              onClick={() => setExpandedLog(expandedLog === log.id ? null : log.id)}
              className="w-full p-4 text-left"
            >
              <div className="flex items-start gap-4">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary/10 to-neon-purple/10 flex items-center justify-center flex-shrink-0 transition-transform duration-300 hover:scale-110 hover:rotate-3">
                  <FileText className="w-4 h-4 text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-card-foreground">
                      {log.action}
                    </span>
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded-lg bg-primary/8 text-primary border border-primary/15">
                      {log.actor}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground line-clamp-1">
                    {log.details}
                  </p>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {formatDistanceToNow(log.timestamp, { addSuffix: true })}
                  </p>
                </div>
                {log.reasoning && (
                  <div className="flex-shrink-0 transition-transform duration-200">
                    {expandedLog === log.id ? (
                      <ChevronUp className="w-4 h-4 text-primary" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-muted-foreground" />
                    )}
                  </div>
                )}
              </div>
            </button>
            {expandedLog === log.id && log.reasoning && (
              <div className="px-4 pb-4 ml-13">
                <div className="p-4 rounded-xl bg-gradient-to-br from-primary/[0.03] to-neon-purple/[0.03] border border-primary/10">
                  <div className="flex items-center gap-2 mb-2">
                    <Brain className="w-3.5 h-3.5 text-primary" />
                    <p className="text-[10px] font-bold text-primary uppercase tracking-[0.15em]">
                      AI Reasoning (Explainable)
                    </p>
                  </div>
                  <p className="text-sm text-card-foreground leading-relaxed">
                    {log.reasoning}
                  </p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
