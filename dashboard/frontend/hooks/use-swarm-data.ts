"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { Agent, Threat, ConsensusDecision, AutomatedResponse } from "@/lib/types";

export function getApiBase(): string {
    if (process.env.NEXT_PUBLIC_API_URL) {
        return process.env.NEXT_PUBLIC_API_URL.trim().replace(/\/+$/, "");
    }

    if (typeof window !== "undefined") {
        const host = window.location.hostname;
        if (host === "localhost" || host === "127.0.0.1") {
            return "http://localhost:8000";
        }
        return "";
    }

    return "http://localhost:8000";
}

const POLL_INTERVAL_MS = 5000;
const WS_RECONNECT_BASE_MS = 2000;
const WS_RECONNECT_MAX_MS = 30000;

const DEFAULT_AGENTS: Agent[] = [
    { id: "AGT-001", name: "Anomaly Sentinel", type: "anomaly", status: "active", trustScore: 94, detectionAccuracy: 97.2, currentLoad: 12, lastActivity: new Date().toISOString(), recentDetections: 4 },
    { id: "AGT-002", name: "Malware Hunter", type: "malware", status: "active", trustScore: 91, detectionAccuracy: 94.8, currentLoad: 8, lastActivity: new Date().toISOString(), recentDetections: 2 },
    { id: "AGT-003", name: "Phishing Guard", type: "phishing", status: "active", trustScore: 89, detectionAccuracy: 92.5, currentLoad: 5, lastActivity: new Date().toISOString(), recentDetections: 1 },
    { id: "AGT-004", name: "DDoS Shield", type: "ddos", status: "active", trustScore: 86, detectionAccuracy: 89.4, currentLoad: 15, lastActivity: new Date().toISOString(), recentDetections: 6 },
    { id: "AGT-005", name: "MITM Detector", type: "mitm", status: "active", trustScore: 92, detectionAccuracy: 95.1, currentLoad: 3, lastActivity: new Date().toISOString(), recentDetections: 0 },
    { id: "AGT-006", name: "Ransom Blocker", type: "ransomware", status: "active", trustScore: 95, detectionAccuracy: 98.0, currentLoad: 7, lastActivity: new Date().toISOString(), recentDetections: 3 },
];

interface SwarmData {
    agents: Agent[];
    threats: Threat[];
    stats: any;
    consensus: ConsensusDecision[];
    responses: AutomatedResponse[];
    mitre: any[];
    attackStats: Record<string, any>;
    logs: any[];
    loading: boolean;
    connected: boolean;
}

export function useSwarmData() {
    const [data, setData] = useState<SwarmData>({
        agents: DEFAULT_AGENTS,
        threats: [],
        stats: {},
        consensus: [],
        responses: [],
        mitre: [],
        attackStats: {},
        logs: [],
        loading: false,
        connected: false,
    });

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectDelay = useRef(WS_RECONNECT_BASE_MS);
    const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const unmounted = useRef(false);
    const lastSuccessfulFetch = useRef<number>(0);

    // Fetch ALL data from REST endpoints
    const fetchAllData = useCallback(async () => {
        const apiBase = getApiBase();
        
        async function fetchJSON(path: string) {
            const res = await fetch(`${apiBase}${path}`, {
                headers: { "Accept": "application/json" },
                signal: AbortSignal.timeout(6000)
            });
            if (!res.ok) throw new Error(`${path} returned ${res.status}`);
            return res.json();
        }

        try {
            const [agents, stats, threats, consensus, responses, mitre, attackStats, logs] = await Promise.all([
                fetchJSON("/api/agents"),
                fetchJSON("/api/stats"),
                fetchJSON("/api/threats"),
                fetchJSON("/api/consensus"),
                fetchJSON("/api/responses"),
                fetchJSON("/api/mitre"),
                fetchJSON("/api/attack_stats"),
                fetchJSON("/api/logs"),
            ]);

            if (unmounted.current) return;
            lastSuccessfulFetch.current = Date.now();

            setData(prev => ({
                agents: Array.isArray(agents) && agents.length > 0 ? agents : prev.agents,
                stats: stats || prev.stats,
                threats: Array.isArray(threats) ? threats : prev.threats,
                consensus: Array.isArray(consensus) ? consensus : prev.consensus,
                responses: Array.isArray(responses) ? responses : prev.responses,
                mitre: Array.isArray(mitre) ? mitre : prev.mitre,
                attackStats: attackStats || prev.attackStats,
                logs: Array.isArray(logs) ? logs : prev.logs,
                loading: false,
                connected: true,
            }));
        } catch (error) {
            if (unmounted.current) return;
            // Only set connected: false if we haven't had a successful fetch in the last 15s
            const isStale = (Date.now() - lastSuccessfulFetch.current) > 15000;
            if (isStale) {
                setData(prev => ({
                    ...prev,
                    loading: false,
                    connected: false,
                }));
            }
        }
    }, []);

    // WebSocket connection with auto-reconnect
    const connectWS = useCallback(() => {
        if (unmounted.current) return;
        
        const apiBase = getApiBase();
        let wsUrl: string;

        if (apiBase) {
            wsUrl = apiBase.replace(/^http/, "ws") + "/ws";
        } else if (typeof window !== "undefined") {
            const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
            wsUrl = `${wsProtocol}//${window.location.host}/ws`;
        } else {
            wsUrl = "ws://localhost:8000/ws";
        }

        if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
            return;
        }

        try {
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onopen = () => {
                if (unmounted.current) { ws.close(); return; }
                reconnectDelay.current = WS_RECONNECT_BASE_MS;
                setData(prev => ({ ...prev, connected: true, loading: false }));
            };

            ws.onmessage = (event) => {
                if (unmounted.current) return;
                try {
                    const message = JSON.parse(event.data);
                    const { type, data: payload } = message;

                    setData(prev => {
                        switch (type) {
                            case "initial_state":
                                return {
                                    ...prev,
                                    agents: payload.agents || prev.agents,
                                    threats: payload.threats || prev.threats,
                                    stats: payload.stats || prev.stats,
                                    consensus: payload.consensus || prev.consensus,
                                    responses: payload.responses || prev.responses,
                                    loading: false,
                                    connected: true,
                                };
                            case "threat_alert":
                                return {
                                    ...prev,
                                    threats: [payload, ...prev.threats].slice(0, 50),
                                };
                            case "agent_update":
                                return {
                                    ...prev,
                                    agents: payload,
                                };
                            case "consensus_update":
                                return {
                                    ...prev,
                                    consensus: [payload, ...prev.consensus].slice(0, 30),
                                };
                            case "response_action":
                                return {
                                    ...prev,
                                    responses: [payload, ...prev.responses].slice(0, 30),
                                    threats: prev.threats.map(t => t.id === payload.threatId ? { ...t, status: "mitigated" } : t)
                                };
                            default:
                                return prev;
                        }
                    });
                } catch { }
            };

            ws.onclose = () => {
                if (unmounted.current) return;
                // Only mark disconnected if REST is also failing
                const isStale = (Date.now() - lastSuccessfulFetch.current) > 15000;
                if (isStale) {
                    setData(prev => ({ ...prev, connected: false }));
                }
                const delay = reconnectDelay.current;
                reconnectDelay.current = Math.min(delay * 2, WS_RECONNECT_MAX_MS);
                reconnectTimer.current = setTimeout(connectWS, delay);
            };

            ws.onerror = () => {};
        } catch { }
    }, []);

    useEffect(() => {
        unmounted.current = false;

        fetchAllData();
        connectWS();

        const pollInterval = setInterval(() => {
            if (!unmounted.current) fetchAllData();
        }, POLL_INTERVAL_MS);

        return () => {
            unmounted.current = true;
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            clearInterval(pollInterval);
            wsRef.current?.close();
        };
    }, [fetchAllData, connectWS]);

    return data;
}
