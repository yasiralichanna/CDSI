"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { Agent, Threat, ConsensusDecision, AutomatedResponse } from "@/lib/types";

export function getApiBase(): string {
    // 1. Next.js environment variable
    if (process.env.NEXT_PUBLIC_API_URL) {
        return process.env.NEXT_PUBLIC_API_URL.trim().replace(/\/+$/, "");
    }

    // 2. Client-side browser execution
    if (typeof window !== "undefined") {
        const host = window.location.hostname;
        if (host === "localhost" || host === "127.0.0.1") {
            return "http://localhost:8000";
        }
        // Deployed environments: use same-origin relative URLs proxied by Next.js rewrites
        return "";
    }

    return "http://localhost:8000";
}

const POLL_INTERVAL_MS = 5000;
const WS_RECONNECT_BASE_MS = 1000;
const WS_RECONNECT_MAX_MS = 30000;

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
        agents: [],
        threats: [],
        stats: {},
        consensus: [],
        responses: [],
        mitre: [],
        attackStats: {},
        logs: [],
        loading: true,
        connected: false,
    });

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectDelay = useRef(WS_RECONNECT_BASE_MS);
    const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const unmounted = useRef(false);

    // Fetch ALL data from REST endpoints
    const fetchAllData = useCallback(async () => {
        const apiBase = getApiBase();
        
        async function fetchJSON(path: string) {
            const res = await fetch(`${apiBase}${path}`, {
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

            setData(prev => ({
                agents,
                stats,
                threats,
                consensus,
                responses,
                mitre,
                attackStats,
                logs,
                loading: false,
                connected: true,
            }));
        } catch (error) {
            if (unmounted.current) return;
            console.warn("CDSI Backend fetch warning:", error);
            setData(prev => ({
                ...prev,
                loading: false,
                connected: false,
            }));
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
                                    agents: payload.agents,
                                    threats: payload.threats,
                                    stats: payload.stats,
                                    consensus: payload.consensus,
                                    responses: payload.responses,
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
                setData(prev => ({ ...prev, connected: false }));
                const delay = reconnectDelay.current;
                reconnectDelay.current = Math.min(delay * 2, WS_RECONNECT_MAX_MS);
                reconnectTimer.current = setTimeout(connectWS, delay);
            };

            ws.onerror = () => {};
        } catch (err) {
            console.warn("WebSocket initialization error:", err);
        }
    }, []);

    useEffect(() => {
        unmounted.current = false;

        const fallbackTimer = setTimeout(() => {
            if (!unmounted.current) {
                setData(prev => ({ ...prev, loading: false }));
            }
        }, 3000);

        fetchAllData();
        connectWS();

        const pollInterval = setInterval(() => {
            if (!unmounted.current) fetchAllData();
        }, POLL_INTERVAL_MS);

        return () => {
            unmounted.current = true;
            clearTimeout(fallbackTimer);
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            clearInterval(pollInterval);
            wsRef.current?.close();
        };
    }, [fetchAllData, connectWS]);

    return data;
}
