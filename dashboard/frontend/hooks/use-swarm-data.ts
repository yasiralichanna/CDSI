"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { Agent, Threat, ConsensusDecision, AutomatedResponse } from "@/lib/types";

export type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "disconnected";

export function getApiBase(): string {
    if (process.env.NEXT_PUBLIC_API_URL) {
        return process.env.NEXT_PUBLIC_API_URL.trim().replace(/\/+$/, "");
    }

    if (typeof window !== "undefined") {
        const host = window.location.hostname;
        if (host === "localhost" || host === "127.0.0.1") {
            return "http://localhost:8000";
        }
        if (host.includes("onrender.com")) {
            return "https://cdsi-backend.onrender.com";
        }
        return "";
    }

    return "https://cdsi-backend.onrender.com";
}

const POLL_INTERVAL_MS = 4000;
const WS_RECONNECT_BASE_MS = 1500;
const WS_RECONNECT_MAX_MS = 25000;
const MAX_RECONNECT_ATTEMPTS = 5;

export interface SwarmData {
    agents: Agent[];
    threats: Threat[];
    stats: any;
    consensus: ConsensusDecision[];
    responses: AutomatedResponse[];
    mitre: any[];
    attackStats: Record<string, any>;
    logs: any[];
    loading: boolean;
    connectionStatus: ConnectionStatus;
    lastUpdated: string | null;
    isStale: boolean;
    apiBaseUrl: string;
}

export function useSwarmData(): SwarmData {
    const [data, setData] = useState<SwarmData>({
        agents: [],
        threats: [],
        stats: {},
        consensus: [],
        responses: [],
        mitre: [],
        attackStats: {},
        logs: [],
        loading: true,
        connectionStatus: "connecting",
        lastUpdated: null,
        isStale: false,
        apiBaseUrl: "https://cdsi-backend.onrender.com",
    });

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectAttempts = useRef<number>(0);
    const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const unmounted = useRef<boolean>(false);
    const lastSuccessfulFetch = useRef<number>(0);

    // Deduplication Helpers
    const mergeUniqueById = useCallback(<T extends { id?: string; threatId?: string }>(
        existing: T[],
        incoming: T[],
        keyField: "id" | "threatId" = "id"
    ): T[] => {
        const seen = new Set<string>();
        const result: T[] = [];
        for (const item of [...incoming, ...existing]) {
            const key = item[keyField];
            if (key) {
                if (!seen.has(key)) {
                    seen.add(key);
                    result.push(item);
                }
            } else {
                result.push(item);
            }
        }
        return result;
    }, []);

    // Fetch ALL data from REST endpoints (Authoritative state recovery)
    const fetchAllData = useCallback(async (isInitial = false) => {
        const apiBase = getApiBase();

        async function fetchJSON(path: string) {
            const res = await fetch(`${apiBase}${path}`, {
                headers: { "Accept": "application/json" },
                signal: AbortSignal.timeout(7000),
            });
            if (!res.ok) throw new Error(`${path} returned status ${res.status}`);
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

            const nowIso = new Date().toISOString();
            lastSuccessfulFetch.current = Date.now();
            reconnectAttempts.current = 0;

            setData(prev => ({
                agents: Array.isArray(agents) ? agents : [],
                stats: stats || {},
                threats: Array.isArray(threats) ? mergeUniqueById(prev.threats, threats, "id") : [],
                consensus: Array.isArray(consensus) ? mergeUniqueById(prev.consensus, consensus, "threatId") : [],
                responses: Array.isArray(responses) ? mergeUniqueById(prev.responses, responses, "id") : [],
                mitre: Array.isArray(mitre) ? mitre : [],
                attackStats: attackStats || {},
                logs: Array.isArray(logs) ? logs : [],
                loading: false,
                connectionStatus: "connected",
                lastUpdated: nowIso,
                isStale: false,
                apiBaseUrl: apiBase,
            }));
        } catch (error) {
            if (unmounted.current) return;

            const timeSinceLastFetch = Date.now() - lastSuccessfulFetch.current;
            const isStale = lastSuccessfulFetch.current > 0 && timeSinceLastFetch > 12000;
            
            reconnectAttempts.current += 1;
            const nextStatus: ConnectionStatus = 
                reconnectAttempts.current > MAX_RECONNECT_ATTEMPTS || (isInitial && lastSuccessfulFetch.current === 0)
                    ? "disconnected"
                    : "reconnecting";

            setData(prev => ({
                ...prev,
                loading: false,
                connectionStatus: nextStatus,
                isStale: isStale || lastSuccessfulFetch.current > 0,
                apiBaseUrl: apiBase,
            }));
        }
    }, [mergeUniqueById]);

    // WebSocket connection with bounded exponential backoff + jitter
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
                reconnectAttempts.current = 0;
                lastSuccessfulFetch.current = Date.now();
                setData(prev => ({
                    ...prev,
                    connectionStatus: "connected",
                    loading: false,
                    isStale: false,
                    lastUpdated: new Date().toISOString(),
                }));
                // Resync state to recover any missed events during disconnect gap
                fetchAllData();
            };

            ws.onmessage = (event) => {
                if (unmounted.current) return;
                lastSuccessfulFetch.current = Date.now();
                const nowIso = new Date().toISOString();

                try {
                    const message = JSON.parse(event.data);
                    const { type, data: payload } = message;

                    if (type === "heartbeat") {
                        setData(prev => ({
                            ...prev,
                            connectionStatus: "connected",
                            isStale: false,
                            lastUpdated: nowIso,
                        }));
                        return;
                    }

                    setData(prev => {
                        switch (type) {
                            case "initial_state":
                                return {
                                    ...prev,
                                    agents: Array.isArray(payload.agents) ? payload.agents : prev.agents,
                                    threats: Array.isArray(payload.threats) ? mergeUniqueById(prev.threats, payload.threats, "id") : prev.threats,
                                    stats: payload.stats || prev.stats,
                                    consensus: Array.isArray(payload.consensus) ? mergeUniqueById(prev.consensus, payload.consensus, "threatId") : prev.consensus,
                                    responses: Array.isArray(payload.responses) ? mergeUniqueById(prev.responses, payload.responses, "id") : prev.responses,
                                    loading: false,
                                    connectionStatus: "connected",
                                    isStale: false,
                                    lastUpdated: nowIso,
                                };
                            case "threat_alert":
                                return {
                                    ...prev,
                                    threats: mergeUniqueById(prev.threats, [payload], "id").slice(0, 50),
                                    connectionStatus: "connected",
                                    isStale: false,
                                    lastUpdated: nowIso,
                                };
                            case "agent_update":
                                return {
                                    ...prev,
                                    agents: payload,
                                    connectionStatus: "connected",
                                    isStale: false,
                                    lastUpdated: nowIso,
                                };
                            case "consensus_update":
                                return {
                                    ...prev,
                                    consensus: mergeUniqueById(prev.consensus, [payload], "threatId").slice(0, 30),
                                    connectionStatus: "connected",
                                    isStale: false,
                                    lastUpdated: nowIso,
                                };
                            case "response_action":
                                return {
                                    ...prev,
                                    responses: mergeUniqueById(prev.responses, [payload], "id").slice(0, 30),
                                    threats: prev.threats.map(t => t.id === payload.threatId ? { ...t, status: "mitigated" as any } : t),
                                    connectionStatus: "connected",
                                    isStale: false,
                                    lastUpdated: nowIso,
                                };
                            default:
                                return prev;
                        }
                    });
                } catch { }
            };

            ws.onclose = () => {
                if (unmounted.current) return;
                wsRef.current = null;
                reconnectAttempts.current += 1;

                const isStale = (Date.now() - lastSuccessfulFetch.current) > 12000;
                const nextStatus: ConnectionStatus = 
                    reconnectAttempts.current > MAX_RECONNECT_ATTEMPTS ? "disconnected" : "reconnecting";

                setData(prev => ({
                    ...prev,
                    connectionStatus: nextStatus,
                    isStale: isStale || prev.isStale,
                }));

                // Bounded exponential backoff + jitter
                const expBackoff = Math.min(WS_RECONNECT_BASE_MS * Math.pow(1.5, reconnectAttempts.current), WS_RECONNECT_MAX_MS);
                const jitter = Math.random() * 1000;
                const delay = expBackoff + jitter;

                reconnectTimer.current = setTimeout(connectWS, delay);
            };

            ws.onerror = () => {};
        } catch { }
    }, [fetchAllData, mergeUniqueById]);

    useEffect(() => {
        unmounted.current = false;

        // Initial fetch and WS connect
        fetchAllData(true);
        connectWS();

        // Interval polling loop
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
