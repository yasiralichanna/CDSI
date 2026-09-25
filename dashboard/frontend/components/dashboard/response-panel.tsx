"use client";

import type { AutomatedResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Ban,
  Server,
  Wifi,
  Globe,
  ArrowRightLeft,
  CheckCircle,
  XCircle,
  ShieldCheck,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";

const actionConfig: Record<AutomatedResponse["action"], { label: string; icon: typeof Ban; description: string }> = {
  ip_blocked: {
    label: "IP Blocked",
    icon: Ban,
    description: "Malicious IP address blacklisted at firewall border to stop unauthorized packets.",
  },
  vm_isolated: {
    label: "VM Isolated",
    icon: Server,
    description: "Compromised Virtual Machine isolated from host network segment to contain spread.",
  },
  iot_quarantined: {
    label: "IoT Quarantined",
    icon: Wifi,
    description: "Vulnerable IoT endpoint placed in restricted VLAN sandbox for traffic monitoring.",
  },
  domain_blocked: {
    label: "Domain Blocked",
    icon: Globe,
    description: "Malicious C2 / phishing domain blacklisted on local DNS sinkhole servers.",
  },
  traffic_rerouted: {
    label: "Traffic Rerouted",
    icon: ArrowRightLeft,
    description: "Suspicious payload streams diverted to honeypot scrubbing center for deep packet analysis.",
  },
};

export function ResponsePanel({ responses = [] }: { responses?: AutomatedResponse[] }) {
  return (
    <div className="card-3d overflow-hidden">
      <div className="flex items-center justify-between p-5 border-b border-border/50">
        <h3 className="text-sm font-semibold text-card-foreground flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
          Automated Responses
        </h3>
        <span className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-success/10 text-success border border-success/20 badge-glow">
          {responses.filter((r) => r.success).length} Successful
        </span>
      </div>
      <div className="divide-y divide-border/30">
        {responses.length === 0 ? (
          <div className="p-12 text-center text-sm text-muted-foreground">
            <div className="w-12 h-12 rounded-2xl bg-success/10 flex items-center justify-center mx-auto mb-3 animate-float">
              <ShieldCheck className="w-6 h-6 text-success" />
            </div>
            No automated responses triggered
          </div>
        ) : (
          responses.map((response) => {
            const action = actionConfig[response.action] || {
              label: response.action,
              icon: ShieldCheck,
              description: "Threat neutralized by automated countermeasure policy.",
            };
            const ActionIcon = action.icon;

            return (
              <div key={response.id} className="p-4 transition-all duration-300 hover:bg-success/[0.02]">
                <div className="flex items-start gap-3">
                  <div className={cn(
                    "w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-300 hover:scale-110",
                    response.success
                      ? "bg-success/10 text-success"
                      : "bg-destructive/10 text-destructive"
                  )}>
                    <ActionIcon className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-card-foreground">{action.label}</span>
                        {response.success ? (
                          <CheckCircle className="w-3.5 h-3.5 text-success" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5 text-destructive" />
                        )}
                      </div>
                      {response.timestamp && (
                        <span className="text-[10px] text-muted-foreground">
                          {formatDistanceToNow(new Date(response.timestamp), { addSuffix: true })}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] font-mono text-primary font-medium mt-0.5">
                      Target Threat: {response.threatId}
                    </p>
                    <div className="mt-2 p-2.5 rounded-lg bg-muted/40 border border-border/30 text-left">
                      <p className="text-xs text-card-foreground/90 font-medium leading-relaxed">
                        {response.details || action.description}
                      </p>
                      <p className="text-[10px] text-muted-foreground mt-1 font-mono">
                        Action Policy: {action.description}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
