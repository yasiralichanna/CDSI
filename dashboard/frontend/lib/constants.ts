/**
 * Shared UI constants — no mock data, just label mappings.
 */
import type { AgentType } from "./types";

export const agentTypeLabels: Record<AgentType, string> = {
  anomaly: "Anomaly Detection",
  malware: "Malware Detection",
  phishing: "Phishing Detection",
  ddos: "DDoS Detection",
  mitm: "MITM Detection",
  ransomware: "Ransomware Detection",
};
