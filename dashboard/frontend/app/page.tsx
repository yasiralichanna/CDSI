"use client";

import { useState } from "react";
import { DashboardHeader } from "@/components/dashboard/header";
import { StatCard } from "@/components/dashboard/stat-card";
import { SwarmVisualization } from "@/components/dashboard/swarm-visualization";
import { AgentTable } from "@/components/dashboard/agent-table";
import { ThreatFeed } from "@/components/dashboard/threat-feed";
import { ConsensusView } from "@/components/dashboard/consensus-view";
import { ResponsePanel } from "@/components/dashboard/response-panel";
import { MitreAttackPanel } from "@/components/dashboard/mitre-attack-panel";
import { AuditLogs } from "@/components/dashboard/audit-logs";
import { AttackTabs } from "@/components/dashboard/attack-tabs";
import { useSwarmData } from "@/hooks/use-swarm-data";
import {
  Bot,
  AlertTriangle,
  Vote,
  Zap,
  Activity,
  LayoutDashboard,
  Users,
  ShieldAlert,
  Network,
  FileStack,
  History,
  Target,
} from "lucide-react";
import { cn } from "@/lib/utils";

type TabId = "overview" | "agents" | "threats" | "consensus" | "attacks" | "responses" | "intel" | "logs";

interface NavItem {
  id: TabId;
  label: string;
  icon: typeof LayoutDashboard;
}

const navItems: NavItem[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "agents", label: "Agents", icon: Users },
  { id: "threats", label: "Threats", icon: ShieldAlert },
  { id: "consensus", label: "Consensus", icon: Network },
  { id: "attacks", label: "Attack Types", icon: Target },
  { id: "responses", label: "Responses", icon: Zap },
  { id: "intel", label: "Intel", icon: FileStack },
  { id: "logs", label: "Logs", icon: History },
];

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const { agents, threats, stats, consensus, responses, mitre, attackStats, logs, loading, connected } = useSwarmData();

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-neon-purple flex items-center justify-center animate-float neon-glow-cyan">
              <Activity className="w-7 h-7 text-white" />
            </div>
            <div className="absolute inset-0 w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-neon-purple animate-ping opacity-20" />
          </div>
          <div className="text-center mt-2">
            <p className="text-sm font-semibold gradient-text">Initializing CDSI Swarm</p>
            <p className="text-[11px] text-muted-foreground mt-1">Connecting to swarm intelligence network...</p>
          </div>
          <div className="flex gap-1.5 mt-2">
            <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: "0ms" }} />
            <div className="w-2 h-2 rounded-full bg-neon-purple animate-bounce" style={{ animationDelay: "150ms" }} />
            <div className="w-2 h-2 rounded-full bg-neon-pink animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
        </div>
      </div>
    );
  }

  const activeAgents = agents.filter((a) => a.status === "active").length;
  const activeThreats = threats.filter((t) => t.status !== "mitigated").length;
  const todayConsensus = consensus.length;
  const todayResponses = responses.length;

  return (
    <div className="min-h-screen bg-background">
      <DashboardHeader />

      <div className="flex">
        {/* Sidebar */}
        <aside className="hidden lg:flex flex-col w-60 border-r border-border/50 glass-panel min-h-[calc(100vh-4rem)] sticky top-16">
          <nav className="flex-1 p-4">
            <div className="space-y-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    className={cn(
                      "w-full flex items-center gap-3 px-3.5 py-2.5 text-sm font-medium rounded-xl transition-all duration-300",
                      activeTab === item.id
                        ? "bg-gradient-to-r from-primary/10 to-neon-purple/5 text-primary border border-primary/15 shadow-sm"
                        : "text-muted-foreground hover:text-foreground hover:bg-muted/50 hover:translate-x-1"
                    )}
                  >
                    <Icon className={cn(
                      "w-4 h-4 transition-transform duration-300",
                      activeTab === item.id && "scale-110"
                    )} />
                    {item.label}
                    {activeTab === item.id && (
                      <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                    )}
                  </button>
                );
              })}
            </div>
          </nav>

          <div className="p-4 border-t border-border/50">
            <div className="p-4 rounded-xl bg-gradient-to-br from-primary/[0.04] to-neon-purple/[0.04] border border-primary/10">
              <div className="flex items-center gap-2 mb-3">
                <Activity className="w-4 h-4 text-primary" />
                <span className="text-[11px] font-bold text-foreground uppercase tracking-wider">System Status</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="relative flex h-2.5 w-2.5">
                  <span className={cn(
                    "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
                    connected ? "bg-success" : "bg-destructive"
                  )} />
                  <span className={cn(
                    "relative inline-flex rounded-full h-2.5 w-2.5",
                    connected ? "bg-success" : "bg-destructive"
                  )} />
                </span>
                <span className={cn(
                  "text-xs font-semibold",
                  connected ? "text-success" : "text-destructive"
                )}>
                  {connected ? "Backend Connected" : "Connection Lost"}
                </span>
              </div>
            </div>
          </div>
        </aside>

        {/* Mobile Nav */}
        <div className="lg:hidden fixed bottom-0 left-0 right-0 z-50 glass-panel border-t border-border/50">
          <div className="flex overflow-x-auto">
            {navItems.slice(0, 5).map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={cn(
                    "flex-1 flex flex-col items-center gap-1 py-3 px-2 text-xs font-semibold transition-all duration-300 min-w-[64px]",
                    activeTab === item.id
                      ? "text-primary"
                      : "text-muted-foreground"
                  )}
                >
                  <Icon className={cn(
                    "w-5 h-5 transition-transform duration-300",
                    activeTab === item.id && "scale-110"
                  )} />
                  <span>{item.label}</span>
                  {activeTab === item.id && (
                    <div className="w-1 h-1 rounded-full bg-primary" />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Main Content */}
        <main className="flex-1 p-6 pb-24 lg:pb-6">
          {activeTab === "overview" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-bold text-foreground tracking-tight">Global Overview</h2>
                <p className="text-sm text-muted-foreground mt-0.5">Real-time swarm intelligence status</p>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                  title="Active Agents"
                  value={`${activeAgents}/${agents.length}`}
                  change={`${agents.filter((a) => a.status === "degraded").length} degraded`}
                  changeType="neutral"
                  icon={Bot}
                  iconColor="text-primary"
                />
                <StatCard
                  title="Active Threats"
                  value={activeThreats}
                  change={`${threats.length} total detected`}
                  changeType={activeThreats > 0 ? "negative" : "positive"}
                  icon={AlertTriangle}
                  iconColor="text-destructive"
                />
                <StatCard
                  title="Consensus Today"
                  value={todayConsensus}
                  change={todayConsensus > 0 ? `${Math.round((consensus.filter(c => c.consensusReached).length / todayConsensus) * 100)}% reached` : "Waiting for events"}
                  changeType={todayConsensus > 0 ? "positive" : "neutral"}
                  icon={Vote}
                  iconColor="text-success"
                />
                <StatCard
                  title="Auto Responses"
                  value={todayResponses}
                  change={todayResponses > 0 ? `${Math.round((responses.filter(r => r.success).length / todayResponses) * 100)}% successful` : "Waiting for events"}
                  changeType={todayResponses > 0 ? "positive" : "neutral"}
                  icon={Zap}
                  iconColor="text-warning"
                />
              </div>

              {/* Main Grid */}
              <div className="grid lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-6">
                  <AgentTable agents={agents} />
                  <ThreatFeed threats={threats} />
                </div>
                <div className="space-y-6">
                  <SwarmVisualization agents={agents} />
                  <ResponsePanel responses={responses} />
                </div>
              </div>
            </div>
          )}

          {activeTab === "agents" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-bold text-foreground tracking-tight">Agent Control Panel</h2>
                <p className="text-sm text-muted-foreground mt-0.5">Monitor and manage all swarm agents</p>
              </div>
              <AgentTable agents={agents} />
              <div className="grid lg:grid-cols-2 gap-6">
                <SwarmVisualization agents={agents} />
                <div className="card-3d p-5">
                  <h3 className="text-sm font-semibold text-card-foreground mb-4 flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                    Agent Performance
                  </h3>
                  <div className="space-y-4">
                    {agents.length === 0 ? (
                      <p className="text-xs text-muted-foreground text-center py-8">No agents active</p>
                    ) : (
                      agents.map((agent) => (
                        <div key={agent.id} className="flex items-center gap-4 group">
                          <div className="w-20">
                            <p className="text-xs font-semibold text-card-foreground group-hover:text-primary transition-colors">{agent.id}</p>
                          </div>
                          <div className="flex-1 h-2.5 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-primary to-neon-purple rounded-full transition-all duration-700"
                              style={{ width: `${agent.detectionAccuracy}%` }}
                            />
                          </div>
                          <span className="text-xs text-muted-foreground w-12 text-right font-semibold">
                            {agent.detectionAccuracy}%
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "threats" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-bold text-foreground tracking-tight">Live Threat Feed</h2>
                <p className="text-sm text-muted-foreground mt-0.5">Real-time threat detection and status</p>
              </div>
              <ThreatFeed threats={threats} />
            </div>
          )}

          {activeTab === "consensus" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-bold text-foreground tracking-tight">Swarm Consensus View</h2>
                <p className="text-sm text-muted-foreground mt-0.5">Trust-weighted voting and decision making</p>
              </div>
              <ConsensusView decisions={consensus} agents={agents} />
            </div>
          )}

          {activeTab === "attacks" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-bold text-foreground tracking-tight">Attack Type Analysis</h2>
                <p className="text-sm text-muted-foreground mt-0.5">Detection trends by attack category</p>
              </div>
              <AttackTabs />
            </div>
          )}

          {activeTab === "responses" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-bold text-foreground tracking-tight">Automated Response Panel</h2>
                <p className="text-sm text-muted-foreground mt-0.5">System actions and rollback options</p>
              </div>
              <ResponsePanel responses={responses} />
            </div>
          )}

          {activeTab === "intel" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-bold text-foreground tracking-tight">Threat Intelligence</h2>
                <p className="text-sm text-muted-foreground mt-0.5">MITRE ATT&CK mapping and kill chain analysis</p>
              </div>
              <MitreAttackPanel />
            </div>
          )}

          {activeTab === "logs" && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-bold text-foreground tracking-tight">Audit Logs</h2>
                <p className="text-sm text-muted-foreground mt-0.5">Complete action history with AI reasoning</p>
              </div>
              <AuditLogs />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
