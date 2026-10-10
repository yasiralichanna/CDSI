"use client";

import { useEffect, useRef, useState } from "react";
import type { Agent, AgentStatus } from "@/lib/types";

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  agent: Agent;
}

const statusColors: Record<AgentStatus, string> = {
  active: "#16a34a",
  degraded: "#d97706",
  offline: "#dc2626",
};

const statusGlowColors: Record<AgentStatus, string> = {
  active: "rgba(22, 163, 74, 0.4)",
  degraded: "rgba(217, 119, 6, 0.3)",
  offline: "rgba(220, 38, 38, 0.4)",
};

export function SwarmVisualization({ agents = [] }: { agents?: Agent[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>(0);
  const nodesRef = useRef<Node[]>([]);
  const [hoveredAgent, setHoveredAgent] = useState<Agent | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resizeCanvas = () => {
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * window.devicePixelRatio;
      canvas.height = rect.height * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    // Initialize nodes
    const centerX = canvas.width / window.devicePixelRatio / 2;
    const centerY = canvas.height / window.devicePixelRatio / 2;
    const radius = Math.min(centerX, centerY) * 0.6;

    nodesRef.current = agents.map((agent, i) => {
      const angle = (i / (agents.length || 1)) * Math.PI * 2;
      return {
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        agent,
      };
    });

    let time = 0;

    const animate = () => {
      const width = canvas.width / window.devicePixelRatio;
      const height = canvas.height / window.devicePixelRatio;
      time += 0.01;

      ctx.clearRect(0, 0, width, height);

      // Draw connections with gradient
      for (let i = 0; i < nodesRef.current.length; i++) {
        for (let j = i + 1; j < nodesRef.current.length; j++) {
          const nodeA = nodesRef.current[i];
          const nodeB = nodesRef.current[j];
          const dx = nodeB.x - nodeA.x;
          const dy = nodeB.y - nodeA.y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < 150) {
            const alpha = (1 - distance / 150) * 0.3;
            const gradient = ctx.createLinearGradient(nodeA.x, nodeA.y, nodeB.x, nodeB.y);
            gradient.addColorStop(0, `rgba(14, 165, 233, ${alpha})`);
            gradient.addColorStop(1, `rgba(139, 92, 246, ${alpha * 0.6})`);
            ctx.strokeStyle = gradient;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(nodeA.x, nodeA.y);
            ctx.lineTo(nodeB.x, nodeB.y);
            ctx.stroke();
          }
        }
      }

      // Draw center hub with animated pulse
      const pulseSize = 30 + Math.sin(time * 2) * 3;
      
      // Outer glow
      const outerGlow = ctx.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, pulseSize * 2);
      outerGlow.addColorStop(0, "rgba(14, 165, 233, 0.08)");
      outerGlow.addColorStop(1, "rgba(14, 165, 233, 0)");
      ctx.fillStyle = outerGlow;
      ctx.beginPath();
      ctx.arc(width / 2, height / 2, pulseSize * 2, 0, Math.PI * 2);
      ctx.fill();

      // Hub circle
      const hubGradient = ctx.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, pulseSize);
      hubGradient.addColorStop(0, "rgba(14, 165, 233, 0.15)");
      hubGradient.addColorStop(1, "rgba(14, 165, 233, 0.03)");
      ctx.fillStyle = hubGradient;
      ctx.beginPath();
      ctx.arc(width / 2, height / 2, pulseSize, 0, Math.PI * 2);
      ctx.fill();

      // Hub border
      ctx.strokeStyle = "rgba(14, 165, 233, 0.4)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(width / 2, height / 2, pulseSize, 0, Math.PI * 2);
      ctx.stroke();

      // Hub text
      ctx.fillStyle = "#0ea5e9";
      ctx.font = "bold 10px Geist";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("SWARM", width / 2, height / 2);

      // Update and draw nodes
      nodesRef.current.forEach((node) => {
        // Apply swarm behavior
        const dx = width / 2 - node.x;
        const dy = height / 2 - node.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        // Attraction to center
        node.vx += dx * 0.0001;
        node.vy += dy * 0.0001;

        // Add some randomness
        node.vx += (Math.random() - 0.5) * 0.1;
        node.vy += (Math.random() - 0.5) * 0.1;

        // Damping
        node.vx *= 0.98;
        node.vy *= 0.98;

        // Update position
        node.x += node.vx;
        node.y += node.vy;

        // Keep within bounds
        const margin = 50;
        if (node.x < margin) node.x = margin;
        if (node.x > width - margin) node.x = width - margin;
        if (node.y < margin) node.y = margin;
        if (node.y > height - margin) node.y = height - margin;

        // Draw node with glow
        const color = statusColors[node.agent.status];
        const glowColor = statusGlowColors[node.agent.status];

        // Neon glow effect
        ctx.shadowColor = glowColor;
        ctx.shadowBlur = 20;

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(node.x, node.y, 8, 0, Math.PI * 2);
        ctx.fill();

        ctx.shadowBlur = 0;

        // White core dot
        ctx.fillStyle = "rgba(255, 255, 255, 0.8)";
        ctx.beginPath();
        ctx.arc(node.x, node.y, 3, 0, Math.PI * 2);
        ctx.fill();

        // Trust score arc
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(node.x, node.y, 13, -Math.PI / 2, -Math.PI / 2 + (node.agent.trustScore / 100) * Math.PI * 2);
        ctx.stroke();

        // Label
        ctx.fillStyle = "#64748b";
        ctx.font = "9px Geist";
        ctx.textAlign = "center";
        ctx.fillText(node.agent.id, node.x, node.y + 24);
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    // Mouse & Touch interaction
    const checkPointForAgent = (clientX: number, clientY: number) => {
      const rect = canvas.getBoundingClientRect();
      const x = clientX - rect.left;
      const y = clientY - rect.top;

      let found: Agent | null = null;
      for (const node of nodesRef.current) {
        const dx = node.x - x;
        const dy = node.y - y;
        if (Math.sqrt(dx * dx + dy * dy) < 22) { // 22px hit area for easy touch targeting
          found = node.agent;
          break;
        }
      }
      setHoveredAgent(found);
    };

    const handleMouseMove = (e: MouseEvent) => {
      checkPointForAgent(e.clientX, e.clientY);
    };

    const handleTouch = (e: TouchEvent) => {
      if (e.touches && e.touches[0]) {
        checkPointForAgent(e.touches[0].clientX, e.touches[0].clientY);
      }
    };

    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("touchstart", handleTouch, { passive: true });
    canvas.addEventListener("touchmove", handleTouch, { passive: true });

    return () => {
      window.removeEventListener("resize", resizeCanvas);
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("touchstart", handleTouch);
      canvas.removeEventListener("touchmove", handleTouch);
      cancelAnimationFrame(animationRef.current);
    };
  }, [agents]);

  return (
    <div className="relative card-3d p-3.5 sm:p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-card-foreground flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
          Swarm Network Status
        </h3>
        <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-mono">
          {agents.length} nodes
        </span>
      </div>
      <div className="relative aspect-[4/3] sm:aspect-square max-h-[340px] rounded-xl overflow-hidden bg-gradient-to-br from-primary/[0.02] to-neon-purple/[0.02]">
        <canvas
          ref={canvasRef}
          className="w-full h-full cursor-crosshair touch-none"
        />
        {hoveredAgent && (
          <div className="absolute top-2 right-2 sm:top-3 sm:right-3 glass-panel rounded-xl p-2.5 sm:p-3 text-[11px] sm:text-xs neon-glow-cyan max-w-[200px] z-10 shadow-lg">
            <p className="font-semibold text-foreground truncate">{hoveredAgent.name}</p>
            <p className="text-muted-foreground mt-0.5 font-mono text-[10px]">ID: {hoveredAgent.id}</p>
            <div className="mt-1 flex items-center justify-between gap-2 text-muted-foreground">
              <span>Trust: <strong className="text-primary">{hoveredAgent.trustScore}%</strong></span>
              <span>Load: <strong className="text-primary">{hoveredAgent.currentLoad}%</strong></span>
            </div>
          </div>
        )}
      </div>
      <div className="flex items-center justify-center flex-wrap gap-3 sm:gap-6 mt-3 sm:mt-4 text-[11px] sm:text-xs">
        <div className="flex items-center gap-1.5 sm:gap-2">
          <div className="w-2 sm:w-2.5 h-2 sm:h-2.5 rounded-full bg-success neon-glow-green" />
          <span className="text-muted-foreground font-medium">Active</span>
        </div>
        <div className="flex items-center gap-1.5 sm:gap-2">
          <div className="w-2 sm:w-2.5 h-2 sm:h-2.5 rounded-full bg-warning" />
          <span className="text-muted-foreground font-medium">Degraded</span>
        </div>
        <div className="flex items-center gap-1.5 sm:gap-2">
          <div className="w-2 sm:w-2.5 h-2 sm:h-2.5 rounded-full bg-destructive neon-glow-red" />
          <span className="text-muted-foreground font-medium">Offline</span>
        </div>
      </div>
    </div>
  );
}

