"use client";

import { agentTypeLabels } from "@/lib/constants";
import type { Agent, ConsensusDecision, ConsensusVote } from "@/lib/types";
import { cn } from "@/lib/utils";
import { CheckCircle, XCircle, HelpCircle, Clock } from "lucide-react";

const voteConfig = {
  threat: { label: "Threat", icon: CheckCircle, class: "text-destructive" },
  safe: { label: "Safe", icon: XCircle, class: "text-success" },
  uncertain: { label: "Uncertain", icon: HelpCircle, class: "text-muted-foreground" },
};

export function ConsensusView({ decisions = [], agents = [] }: { decisions?: ConsensusDecision[], agents?: Agent[] }) {
  const decision = decisions[0];

  if (!decision) {
    return (
      <div className="card-3d p-12 text-center">
        <div className="w-14 h-14 rounded-2xl bg-primary/8 flex items-center justify-center mx-auto mb-4 animate-float">
          <Clock className="w-7 h-7 text-primary" />
        </div>
        <p className="text-sm text-muted-foreground font-medium">Waiting for consensus requests...</p>
      </div>
    );
  }

  const threatVotes = decision.votes.filter((v) => v.vote === "threat").length;
  const safeVotes = decision.votes.filter((v) => v.vote === "safe").length;
  const uncertainVotes = decision.votes.filter((v) => v.vote === "uncertain").length;

  return (
    <div className="card-3d overflow-hidden">
      <div className="flex items-center justify-between p-5 border-b border-border/50">
        <h3 className="text-sm font-semibold text-card-foreground flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-neon-purple animate-pulse" />
          Swarm Consensus View
        </h3>
        <span className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-primary/8 text-primary border border-primary/15 font-mono">
          {decision.threatId}
        </span>
      </div>

      <div className="p-5">
        {/* Consensus Summary */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          <div className="text-center p-4 rounded-xl bg-muted/50 border border-border/30 transition-all duration-300 hover:bg-primary/[0.03] hover:border-primary/20">
            <p className="text-2xl font-bold text-card-foreground">{decision.votes.length}</p>
            <p className="text-[11px] text-muted-foreground font-medium mt-1">Total Votes</p>
          </div>
          <div className="text-center p-4 rounded-xl bg-destructive/[0.04] border border-destructive/10 transition-all duration-300 hover:bg-destructive/[0.08]">
            <p className="text-2xl font-bold text-destructive">{threatVotes}</p>
            <p className="text-[11px] text-muted-foreground font-medium mt-1">Threat Votes</p>
          </div>
          <div className="text-center p-4 rounded-xl bg-primary/[0.04] border border-primary/10 transition-all duration-300 hover:bg-primary/[0.08]">
            <p className="text-2xl font-bold text-primary">{decision.trustWeightedScore.toFixed(1)}%</p>
            <p className="text-[11px] text-muted-foreground font-medium mt-1">Weighted Score</p>
          </div>
          <div className="text-center p-4 rounded-xl bg-success/[0.04] border border-success/10 transition-all duration-300 hover:bg-success/[0.08]">
            <p className="text-2xl font-bold text-success">{decision.timeToConsensus}ms</p>
            <p className="text-[11px] text-muted-foreground font-medium mt-1">Latency</p>
          </div>
        </div>

        {/* Final Decision */}
        <div className={cn(
          "mb-6 p-5 rounded-xl border-2 transition-all duration-300",
          decision.finalDecision === "threat" && "border-destructive/40 bg-destructive/[0.04] neon-glow-red",
          decision.finalDecision === "safe" && "border-success/40 bg-success/[0.04] neon-glow-green",
          decision.finalDecision === "uncertain" && "border-muted bg-muted/10",
          !decision.finalDecision && "border-warning/40 bg-warning/[0.04]"
        )}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-[0.15em] font-bold">Status</p>
              <p className={cn(
                "text-xl font-bold uppercase tracking-wider mt-1",
                decision.finalDecision === "threat" && "text-destructive",
                decision.finalDecision === "safe" && "text-success",
                decision.finalDecision === "uncertain" && "text-muted-foreground",
                !decision.finalDecision && "text-warning"
              )}>
                {decision.finalDecision || "PENDING"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {decision.consensusReached ? (
                <>
                  <CheckCircle className="w-5 h-5 text-success" />
                  <span className="text-sm text-success font-semibold">Consensus Reached</span>
                </>
              ) : (
                <>
                  <Clock className="w-5 h-5 text-warning animate-spin" />
                  <span className="text-sm text-warning font-semibold">Voting in Progress</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Individual Votes */}
        <div>
          <p className="text-[10px] text-muted-foreground mb-3 uppercase tracking-[0.15em] font-bold">Agent Votes (Trust-Weighted)</p>
          <div className="space-y-2">
            {decision.votes.map((vote) => {
              const agent = agents.find((a) => a.id === vote.agentId);
              return (
                <VoteBar key={vote.agentId} vote={vote} agent={agent} />
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function VoteBar({ vote, agent }: { vote: ConsensusVote; agent?: Agent }) {
  const voteInfo = voteConfig[vote.vote as keyof typeof voteConfig] || voteConfig.uncertain;
  const VoteIcon = voteInfo.icon;
  const trustWeight = agent?.trustScore || 50;

  return (
    <div className="flex items-center gap-3 p-3 rounded-xl bg-muted/30 border border-border/30 hover:bg-primary/[0.03] hover:border-primary/15 transition-all duration-300">
      <div className="w-20 flex-shrink-0">
        <p className="text-xs font-semibold text-card-foreground">{vote.agentId}</p>
        <p className="text-[10px] text-muted-foreground">{agentTypeLabels[vote.agentType] || vote.agentType}</p>
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <div className="flex-1 h-2.5 bg-muted rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-700",
                vote.vote === "threat" && "bg-destructive",
                vote.vote === "safe" && "bg-success",
                vote.vote === "uncertain" && "bg-muted-foreground"
              )}
              style={{ width: `${vote.confidence}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground w-10 text-right font-medium">{vote.confidence}%</span>
        </div>
        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <span>Trust Weight: <span className="font-semibold text-foreground/70">{trustWeight}%</span></span>
          <span>Effective: <span className="font-bold text-primary">{((vote.confidence * trustWeight) / 100).toFixed(1)}%</span></span>
        </div>
      </div>
      <VoteIcon className={cn("w-5 h-5 flex-shrink-0 transition-transform duration-300 hover:scale-125", voteInfo.class)} />
    </div>
  );
}
