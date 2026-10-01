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
const WS_RECONNECT_BASE_MS = 2000;
const WS_RECONNECT_MAX_MS = 20000;

async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 10000): Promise<Response> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal,
        });
        return response;
    } finally {
        clearTimeout(timer);
    }
}

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
    const restFailures = useRef<number>(0);
    const wsReconnectAttempts = useRef<number>(0);
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

    // Fetch ALL data from REST endpoints with single aggregated state optimization + fallback
    const fetchAllData = useCallback(async (isInitial = false) => {
        const apiBase = getApiBase();
        const urlsToTry = [
            `${apiBase}/api/state?_t=${Date.now()}`,
            `/api/state?_t=${Date.now()}`
        ];

        const hasFetchedBefore = lastSuccessfulFetch.current > 0;
        const fetchTimeoutMs = hasFetchedBefore ? 10000 : 25000;

        // Priority 1: Try /api/state aggregated endpoint (direct backend URL or relative proxy)
        for (const url of urlsToTry) {
            try {
                const res = await fetchWithTimeout(url, {
                    headers: { 
                        "Accept": "application/json",
                        "Cache-Control": "no-cache, no-store, must-revalidate"
                    },
                }, fetchTimeoutMs);

                if (res.ok) {
                    const state = await res.json();
                    if (unmounted.current) return;

                    const nowIso = new Date().toISOString();
                    lastSuccessfulFetch.current = Date.now();
                    restFailures.current = 0;

                    setData(prev => ({
                        agents: Array.isArray(state.agents) ? state.agents : [],
                        stats: state.stats || {},
                        threats: Array.isArray(state.threats) ? mergeUniqueById(prev.threats, state.threats, "id") : [],
                        consensus: Array.isArray(state.consensus) ? mergeUniqueById(prev.consensus, state.consensus, "threatId") : [],
                        responses: Array.isArray(state.responses) ? mergeUniqueById(prev.responses, state.responses, "id") : [],
                        mitre: Array.isArray(state.mitre) ? state.mitre : [],
                        attackStats: state.attackStats || {},
                        logs: Array.isArray(state.logs) ? state.logs : [],
                        loading: false,
                        connectionStatus: "connected",
                        lastUpdated: nowIso,
                        isStale: false,
                        apiBaseUrl: apiBase || "https://cdsi-backend.onrender.com",
                    }));
                    return;
                }
            } catch {
                // Try next URL in urlsToTry loop
            }
        }

        // Priority 2 Fallback: Promise.allSettled for individual micro endpoints
        async function fetchJSON(path: string) {
            const primaryUrl = `${apiBase}${path}?_t=${Date.now()}`;
            try {
                const res = await fetchWithTimeout(primaryUrl, {
                    headers: { 
                        "Accept": "application/json",
                        "Cache-Control": "no-cache, no-store, must-revalidate"
                    },
                }, 8000);
                if (res.ok) return res.json();
            } catch {}

            // Fallback to relative path
            const relRes = await fetchWithTimeout(`${path}?_t=${Date.now()}`, {
                headers: { 
                    "Accept": "application/json",
                    "Cache-Control": "no-cache, no-store, must-revalidate"
                },
            }, 8000);
            if (!relRes.ok) throw new Error(`${path} returned status ${relRes.status}`);
            return relRes.json();
        }

        try {
            const results = await Promise.allSettled([
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

            const [agentsRes, statsRes, threatsRes, consensusRes, responsesRes, mitreRes, attackStatsRes, logsRes] = results;
            const anySuccess = results.some(r => r.status === "fulfilled");
            if (!anySuccess) throw new Error("All REST endpoints failed");

            const nowIso = new Date().toISOString();
            lastSuccessfulFetch.current = Date.now();
            restFailures.current = 0;

            setData(prev => ({
                agents: agentsRes.status === "fulfilled" && Array.isArray(agentsRes.value) ? agentsRes.value : prev.agents,
                stats: statsRes.status === "fulfilled" ? statsRes.value : prev.stats,
                threats: threatsRes.status === "fulfilled" && Array.isArray(threatsRes.value) ? mergeUniqueById(prev.threats, threatsRes.value, "id") : prev.threats,
                consensus: consensusRes.status === "fulfilled" && Array.isArray(consensusRes.value) ? mergeUniqueById(prev.consensus, consensusRes.value, "threatId") : prev.consensus,
                responses: responsesRes.status === "fulfilled" && Array.isArray(responsesRes.value) ? mergeUniqueById(prev.responses, responsesRes.value, "id") : prev.responses,
                mitre: mitreRes.status === "fulfilled" && Array.isArray(mitreRes.value) ? mitreRes.value : prev.mitre,
                attackStats: attackStatsRes.status === "fulfilled" ? attackStatsRes.value : prev.attackStats,
                logs: logsRes.status === "fulfilled" && Array.isArray(logsRes.value) ? logsRes.value : prev.logs,
                loading: false,
                connectionStatus: "connected",
                lastUpdated: nowIso,
                isStale: false,
                apiBaseUrl: apiBase || "https://cdsi-backend.onrender.com",
            }));
        } catch (error) {
            if (unmounted.current) return;

            restFailures.current += 1;
            const timeSinceLastFetch = Date.now() - lastSuccessfulFetch.current;
            const hasFetchedBefore = lastSuccessfulFetch.current > 0;
            const isStale = hasFetchedBefore && timeSinceLastFetch > 25000;

            let nextStatus: ConnectionStatus;
            let keepLoading = false;

            if (!hasFetchedBefore) {
                // Cold start window: allow up to 10 retry cycles (~60s) before marking disconnected
                if (restFailures.current > 10) {
                    nextStatus = "disconnected";
                    keepLoading = false;
                } else {
                    nextStatus = "connecting";
                    keepLoading = true; // keep loading indicator visible during backend warmup
                }
            } else if (timeSinceLastFetch > 20000) {
                nextStatus = restFailures.current > 5 ? "disconnected" : "reconnecting";
                keepLoading = false;
            } else {
                nextStatus = "connected";
                keepLoading = false;
            }

            setData(prev => ({
                ...prev,
                loading: keepLoading,
                connectionStatus: nextStatus,
                isStale: isStale,
                apiBaseUrl: apiBase || "https://cdsi-backend.onrender.com",
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
                wsReconnectAttempts.current = 0;
                lastSuccessfulFetch.current = Date.now();
                setData(prev => ({
                    ...prev,
                    connectionStatus: "connected",
                    loading: false,
                    isStale: false,
                    lastUpdated: new Date().toISOString(),
                }));
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
                wsReconnectAttempts.current += 1;

                const restIsHealthy = (Date.now() - lastSuccessfulFetch.current) < 15000;

                // Only degrade connection status if REST polling is ALSO not healthy
                if (!restIsHealthy) {
                    const isStale = (Date.now() - lastSuccessfulFetch.current) > 20000;
                    const hasFetchedBefore = lastSuccessfulFetch.current > 0;

                    let nextStatus: ConnectionStatus;
                    if (!hasFetchedBefore) {
                        nextStatus = "connecting";
                    } else if (isStale) {
                        nextStatus = "disconnected";
                    } else {
                        nextStatus = "reconnecting";
                    }

                    setData(prev => ({
                        ...prev,
                        connectionStatus: nextStatus,
                        isStale: isStale && prev.lastUpdated !== null,
                    }));
                }

                // Schedule background WS reconnection attempt
                const expBackoff = Math.min(WS_RECONNECT_BASE_MS * Math.pow(1.5, wsReconnectAttempts.current), WS_RECONNECT_MAX_MS);
                const jitter = Math.random() * 1000;
                const delay = expBackoff + jitter;

                reconnectTimer.current = setTimeout(connectWS, delay);
            };

            ws.onerror = () => {};
        } catch { }
    }, [fetchAllData, mergeUniqueById]);

    useEffect(() => {
        unmounted.current = false;

        fetchAllData(true);
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

