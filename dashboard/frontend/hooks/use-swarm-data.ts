"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { Agent, Threat, ConsensusDecision, AutomatedResponse } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = API_BASE.replace(/^http/, "ws") + "/ws";
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

async function fetchJSON(path: string) {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) throw new Error(`${path} returned ${res.status}`);
    return res.json();
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
    const fetchAllData = useCallback(async (isInitial = false) => {
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
                connected: prev.connected,
            }));
        } catch (error) {
            console.error("Failed to fetch data:", error);
            if (isInitial) {
                // Retry initial load after 2s if the backend isn't ready yet
                if (!unmounted.current) {
                    setTimeout(() => { if (!unmounted.current) fetchAllData(true); }, 2000);
                }
            }
        }
    }, []);

    // WebSocket connection with auto-reconnect
    const connectWS = useCallback(() => {
        if (unmounted.current) return;
        if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return;

        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
            if (unmounted.current) { ws.close(); return; }
            reconnectDelay.current = WS_RECONNECT_BASE_MS; // Reset backoff on success
            setData(prev => ({ ...prev, connected: true }));
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
            // Auto-reconnect with exponential backoff
            const delay = reconnectDelay.current;
            reconnectDelay.current = Math.min(delay * 2, WS_RECONNECT_MAX_MS);
            reconnectTimer.current = setTimeout(connectWS, delay);
        };

        ws.onerror = () => {
            // onclose will fire after onerror, which triggers reconnect
        };
    }, []);

    useEffect(() => {
        unmounted.current = false;

        // Initial data fetch (retries automatically if backend isn't ready)
        fetchAllData(true);

        // Connect WebSocket with auto-reconnect
        connectWS();

        // Poll ALL data every 5 seconds as a reliable fallback
        const pollInterval = setInterval(() => {
            if (!unmounted.current) fetchAllData();
        }, POLL_INTERVAL_MS);

        return () => {
            unmounted.current = true;
            wsRef.current?.close();
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            clearInterval(pollInterval);
        };
    }, [fetchAllData, connectWS]);

    return data;
}
