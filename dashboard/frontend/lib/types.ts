export type AgentType = 
  | "anomaly"
  | "malware"
  | "phishing"
  | "ddos"
  | "mitm"
  | "ransomware";

export type AgentStatus = "active" | "degraded" | "offline";

export type ThreatSeverity = "low" | "medium" | "high" | "critical";

export type ThreatStatus = 
  | "pending_consensus"
  | "confirmed"
  | "mitigated"
  | "false_positive";

export interface Agent {
  id: string;
  name: string;
  type: AgentType;
  status: AgentStatus;
  trustScore: number;
  detectionAccuracy: number;
  currentLoad: number;
  lastActivity: Date;
  recentDetections: number;
}

export interface Threat {
  id: string;
  type: AgentType;
  detectedBy: string[];
  severity: ThreatSeverity;
  confidence: number;
  timestamp: Date;
  status: ThreatStatus;
  description: string;
  sourceIP?: string;
  targetIP?: string;
  metadata?: {
    features?: Record<string, number | string>;
    [key: string]: any;
  };
}

export interface ConsensusVote {
  agentId: string;
  agentType: AgentType;
  vote: "threat" | "safe" | "uncertain";
  confidence: number;
  timestamp: Date;
}

export interface ConsensusDecision {
  threatId: string;
  votes: ConsensusVote[];
  finalDecision: "threat" | "safe" | "uncertain";
  consensusReached: boolean;
  timeToConsensus: number; // in ms
  trustWeightedScore: number;
}

export interface AutomatedResponse {
  id: string;
  threatId: string;
  action: "ip_blocked" | "vm_isolated" | "iot_quarantined" | "domain_blocked" | "traffic_rerouted";
  timestamp: Date;
  success: boolean;
  canRollback: boolean;
  details: string;
}

export interface MitreAttackTechnique {
  id: string;
  name: string;
  tactic: string;
  killChainPhase: string;
  threatCount: number;
}

export interface AuditLog {
  id: string;
  timestamp: Date;
  actor: string;
  action: string;
  details: string;
  reasoning?: string;
}
