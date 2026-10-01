"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { Agent, Threat, ConsensusDecision, AutomatedResponse } from "@/lib/types";

export function getApiBase(): string {
    if (typeof window !== "undefined") {
        // 1. Check custom user backend URL from settings
        const custom = localStorage.getItem("CDSI_BACKEND_URL");
        if (custom && custom.trim() !== "") {
            return custom.trim().replace(/\/+$/, "");
        }

        // 2. Build-time env var
        if (process.env.NEXT_PUBLIC_API_URL) {
            return process.env.NEXT_PUBLIC_API_URL.trim().replace(/\/+$/, "");
        }

        const host = window.location.hostname;
        const protocol = window.location.protocol;

        // 3. Localhost dev
        if (host === "localhost" || host === "127.0.0.1") {
            return "http://localhost:8000";
        }

        // 4. Render deployment auto-detection
        if (host.includes("onrender.com")) {
            if (host.includes("frontend")) return `${protocol}//${host.replace("frontend", "backend")}`;
            if (host.includes("web")) return `${protocol}//${host.replace("web", "backend")}`;
            if (host.includes("ui")) return `${protocol}//${host.replace("ui", "backend")}`;
            if (host.includes("app")) return `${protocol}//${host.replace("app", "backend")}`;
            
            // Fallback pattern: if name is e.g. my-cdsi.onrender.com -> try my-cdsi-backend.onrender.com
            const parts = host.split(".");
            return `${protocol}//${parts[0]}-backend.${parts.slice(1).join(".")}`;
        }

        // 5. Generic auto-replacement
        return `${protocol}//${host.replace(/frontend|ui|web|app/i, "backend")}`;
    }

    return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
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
    apiBaseUrl: string;
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
        apiBaseUrl: "http://localhost:8000",
    });

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectDelay = useRef(WS_RECONNECT_BASE_MS);
    const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const unmounted = useRef(false);

    // Fetch ALL data from REST endpoints
    const fetchAllData = useCallback(async () => {
        const currentApiBase = getApiBase();
        
        async function fetchJSON(path: string) {
            const res = await fetch(`${currentApiBase}${path}`, {
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
                apiBaseUrl: currentApiBase,
            }));
        } catch (error) {
            if (unmounted.current) return;
            console.warn("CDSI Backend fetch warning:", error);
            // Ensure loading is set to false after failure so user sees dashboard with disconnection indicator
            setData(prev => ({
                ...prev,
                loading: false,
                connected: false,
                apiBaseUrl: currentApiBase,
            }));
        }
    }, []);

    // WebSocket connection with auto-reconnect
    const connectWS = useCallback(() => {
        if (unmounted.current) return;
        
        const currentApiBase = getApiBase();
        const wsUrl = currentApiBase.replace(/^http/, "ws") + "/ws";

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

        // Dynamic API Base state
        setData(prev => ({ ...prev, apiBaseUrl: getApiBase() }));

        // Safety timeout: set loading to false after 3 seconds max so user is NEVER stuck on loading screen
        const fallbackTimer = setTimeout(() => {
            if (!unmounted.current) {
                setData(prev => ({ ...prev, loading: false }));
            }
        }, 3000);

        // Fetch immediately
        fetchAllData();
        connectWS();

        // Interval polling fallback
        const pollInterval = setInterval(() => {
            if (!unmounted.current) fetchAllData();
        }, POLL_INTERVAL_MS);

        // Listen for backend URL change events from header settings
        const handleUrlChange = () => {
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
            setData(prev => ({ ...prev, loading: true, apiBaseUrl: getApiBase() }));
            fetchAllData();
            connectWS();
        };

        window.addEventListener("cdsi_backend_url_changed", handleUrlChange);

        return () => {
            unmounted.current = true;
            clearTimeout(fallbackTimer);
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            clearInterval(pollInterval);
            wsRef.current?.close();
            window.removeEventListener("cdsi_backend_url_changed", handleUrlChange);
        };
    }, [fetchAllData, connectWS]);

    return data;
}
