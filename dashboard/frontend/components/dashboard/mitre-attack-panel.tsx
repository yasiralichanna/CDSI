"use client";

import { useSwarmData } from "@/hooks/use-swarm-data";
import { cn } from "@/lib/utils";

const killChainPhases = [
  "Reconnaissance",
  "Weaponization",
  "Delivery",
  "Exploitation",
  "Installation",
  "C2",
  "Actions",
];

const phaseColors: Record<string, string> = {
  Reconnaissance: "bg-chart-1/10 text-chart-1 border-chart-1/20",
  Weaponization: "bg-chart-2/10 text-chart-2 border-chart-2/20",
  Delivery: "bg-chart-3/10 text-chart-3 border-chart-3/20",
  Exploitation: "bg-chart-4/10 text-chart-4 border-chart-4/20",
  Installation: "bg-chart-5/10 text-chart-5 border-chart-5/20",
  C2: "bg-primary/10 text-primary border-primary/20",
  Actions: "bg-destructive/10 text-destructive border-destructive/20",
};

export function MitreAttackPanel() {
  const { mitre } = useSwarmData();
  const mitreAttackTechniques = mitre || [];
  
  return (
    <div className="card-3d overflow-hidden">
      <div className="flex items-center justify-between p-5 border-b border-border/50">
        <div>
          <h3 className="text-sm font-semibold text-card-foreground flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-neon-purple animate-pulse" />
            MITRE ATT&CK Mapping
          </h3>
          <p className="text-[11px] text-muted-foreground mt-0.5">Detected techniques mapped to kill chain</p>
        </div>
      </div>
      
      <div className="p-3.5 sm:p-5">
        {/* Kill Chain Timeline */}
        <div className="mb-4 sm:mb-6">
          <p className="text-[10px] text-muted-foreground mb-2 sm:mb-3 uppercase tracking-[0.15em] font-bold">Kill Chain Phases</p>
          <div className="flex items-center gap-1 overflow-x-auto pb-2 no-scrollbar touch-scroll">
            {killChainPhases.map((phase, i) => {
              const techniques = mitreAttackTechniques.filter((t) => t.killChainPhase === phase);
              const hasThreats = techniques.length > 0;
              
              return (
                <div key={phase} className="flex items-center flex-shrink-0">
                  <div className={cn(
                    "px-2.5 py-2 sm:px-3 sm:py-2.5 rounded-xl text-[10px] sm:text-[11px] font-bold whitespace-nowrap border transition-all duration-300 cursor-default",
                    hasThreats 
                      ? cn(phaseColors[phase], "hover:scale-105 hover:shadow-md") 
                      : "bg-muted/50 text-muted-foreground border-border/30 hover:bg-muted"
                  )}>
                    <span>{phase}</span>
                    {hasThreats && (
                      <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-white/60 text-[10px] font-bold">
                        {techniques.reduce((sum, t) => sum + t.threatCount, 0)}
                      </span>
                    )}
                  </div>
                  {i < killChainPhases.length - 1 && (
                    <div className="w-3 sm:w-4 h-0.5 bg-gradient-to-r from-primary/20 to-transparent flex-shrink-0" />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Technique Grid */}
        <div>
          <p className="text-[10px] text-muted-foreground mb-3 uppercase tracking-[0.15em] font-bold">Detected Techniques</p>
          <div className="grid gap-2">
            {mitreAttackTechniques.map((technique) => (
              <div
                key={technique.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between p-3 sm:p-4 rounded-xl bg-muted/30 border border-border/30 hover:bg-primary/[0.03] hover:border-primary/15 transition-all duration-300 gap-2.5 sm:gap-3 group"
              >
                <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
                  <span className="text-[11px] font-mono text-primary font-bold flex-shrink-0">{technique.id}</span>
                  <div className="min-w-0">
                    <p className="text-xs sm:text-sm font-semibold text-card-foreground group-hover:text-primary transition-colors truncate">{technique.name}</p>
                    <p className="text-[10px] sm:text-[11px] text-muted-foreground">{technique.tactic}</p>
                  </div>
                </div>
                <div className="flex items-center justify-between sm:justify-end gap-3 pt-2 sm:pt-0 border-t border-border/20 sm:border-0">
                  <span className={cn(
                    "px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-lg text-[9px] sm:text-[10px] font-bold border transition-all duration-300 group-hover:scale-105",
                    phaseColors[technique.killChainPhase]
                  )}>
                    {technique.killChainPhase}
                  </span>
                  <div className="text-right">
                    <p className="text-xs sm:text-sm font-bold text-card-foreground">{technique.threatCount} <span className="sm:hidden text-[10px] text-muted-foreground font-normal">det.</span></p>
                    <p className="hidden sm:block text-[10px] text-muted-foreground">detections</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

    </div>
  );
}
