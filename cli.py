"""
CDSI CLI — Command-line interface for training, serving, and management.

Usage:
    python cli.py train --agent ddos
    python cli.py train --all
    python cli.py serve
    python cli.py download --agent ddos
    python cli.py status
    python cli.py ingest --sample ddos
    python cli.py ingest --pcap data.pcap

"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # Fix encoding for Rich console on Windows (cp1252 can't handle emoji)
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console(force_terminal=True)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


@click.group()
def cli():
    """CDSI — Cyber Defense Swarm Intelligence CLI"""
    pass


@cli.command()
@click.option("--agent", type=str, help="Agent type to train (ddos, anomaly, malware, phishing, mitm, ransomware)")
@click.option("--all", "train_all", is_flag=True, help="Train all agents")
@click.option("--tune", is_flag=True, help="Enable hyperparameter tuning")
def train(agent: str, train_all: bool, tune: bool):
    """Train agent models on real datasets."""
    from config.settings import get_settings

    settings = get_settings()

    if train_all:
        agents_to_train = ["ddos", "anomaly", "malware", "phishing", "mitm", "ransomware"]
    elif agent:
        agents_to_train = [agent]
    else:
        console.print("[red]Specify --agent TYPE or --all[/red]")
        return

    for agent_type in agents_to_train:
        console.print(f"\n[bold cyan]Training {agent_type} agent...[/bold cyan]")
        try:
            agent_instance = _create_agent(agent_type)
            metrics = agent_instance.train()

            table = Table(title=f"{agent_type.upper()} Training Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            for k, v in metrics.items():
                table.add_row(k, f"{v:.4f}")
            console.print(table)

        except FileNotFoundError as e:
            console.print(f"[yellow]⚠ Dataset not found for {agent_type}: {e}[/yellow]")
            console.print(f"  Run: [bold]python cli.py download --agent {agent_type}[/bold]")
        except Exception as e:
            console.print(f"[red]✗ Error training {agent_type}: {e}[/red]")


@cli.command()
@click.option("--agent", type=str, help="Dataset to download")
@click.option("--all", "download_all", is_flag=True, help="Download all datasets")
@click.option("--force", is_flag=True, help="Force re-download")
def download(agent: str, download_all: bool, force: bool):
    """Download training datasets."""
    from datasets.downloader import DatasetDownloader

    downloader = DatasetDownloader()

    if download_all:
        console.print("[bold cyan]Downloading all datasets...[/bold cyan]")
        results = downloader.download_all(force=force)
        for agent_type, path in results.items():
            console.print(f"  [green]✓[/green] {agent_type}: {path}")
    elif agent:
        console.print(f"[bold cyan]Downloading {agent} dataset...[/bold cyan]")
        path = downloader.download_dataset(agent, force=force)
        console.print(f"  [green]✓[/green] {agent}: {path}")
    else:
        console.print("[red]Specify --agent TYPE or --all[/red]")


@cli.command()
@click.option("--agent", type=str, help="Preprocess dataset for agent")
@click.option("--all", "preprocess_all", is_flag=True, help="Preprocess all")
def preprocess(agent: str, preprocess_all: bool):
    """Preprocess downloaded datasets into ML-ready format."""
    from datasets.preprocessor import DatasetPreprocessor

    agents = ["ddos", "anomaly", "malware", "phishing", "mitm", "ransomware"] if preprocess_all else [agent]

    for agent_type in agents:
        if not agent_type:
            continue
        console.print(f"[bold cyan]Preprocessing {agent_type}...[/bold cyan]")
        try:
            preprocessor = DatasetPreprocessor(agent_type)
            outputs = preprocessor.preprocess()
            console.print(f"  [green]✓[/green] Output: {outputs.get('csv', 'done')}")
        except Exception as e:
            console.print(f"  [red]✗ Error: {e}[/red]")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, type=int, help="Port to listen on")
@click.option("--reload", is_flag=True, help="Enable hot-reload")
def serve(host: str, port: int, reload: bool):
    """Start the CDSI backend API server."""
    import uvicorn

    console.print(Panel.fit(
        "[bold cyan]CDSI — Cyber Defense Swarm Intelligence[/bold cyan]\n"
        f"Starting API server on [green]{host}:{port}[/green]\n"
        f"Swagger UI: [blue]http://{host}:{port}/docs[/blue]\n"
        f"WebSocket: [blue]ws://{host}:{port}/ws[/blue]",
        title="🛡️ CDSI Server",
    ))

    uvicorn.run(
        "dashboard.backend.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@cli.command("start_all")
@click.option("--host", default="0.0.0.0", help="Host to bind API to")
@click.option("--port", default=8000, type=int, help="Port to listen on")
def start_all(host: str, port: int):
    """Start the API server and all real agent processes locally."""
    import subprocess
    import time

    console.print(Panel.fit(
        "[bold cyan]CDSI — Starting Full Platform Local Deployment[/bold cyan]\n"
        "Spawning API server and 6 standalone agent processes.",
        title="🛡️ CDSI Start-All",
    ))

    # Agents to start
    agents = ["ddos", "anomaly", "malware", "phishing", "mitm", "ransomware"]
    processes = []

    try:
        # Start API server
        api_cmd = [sys.executable, "cli.py", "serve", "--host", host, "--port", str(port)]
        api_proc = subprocess.Popen(api_cmd)
        processes.append(("API Server", api_proc))

        # Wait a moment for ZeroMQ broker to bind in the API
        time.sleep(2)

        # Start agents
        for agent in agents:
            cmd = [sys.executable, "agent_runner.py", agent]
            proc = subprocess.Popen(cmd)
            processes.append((f"Agent-{agent.upper()}", proc))
            time.sleep(0.5)

        console.print("[bold green]All processes started. Press Ctrl+C to terminate all.[/bold green]")

        # Keep alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Shutting down all processes...[/bold yellow]")
        for name, proc in processes:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        console.print("[bold green]Shutdown complete.[/bold green]")


@cli.command()
@click.option("--pcap", type=click.Path(exists=True), help="PCAP file to ingest")
@click.option("--sample", type=click.Choice(["ddos", "anomaly", "malware", "phishing", "mitm", "ransomware"]), help="Generate sample events of type")
@click.option("--count", default=10, help="Number of sample events to generate")
@click.option("--interval", default=1.0, help="Seconds between events")
@click.option("--topic", default=None, help="Override ZMQ topic")
def ingest(pcap: str | None, sample: str | None, count: int, interval: float, topic: str | None):
    """Ingest network traffic or sample events into the platform."""
    from ingestion.collectors.pcap import PCAPCollector
    from ingestion.router import EventRouter
    from comms.zeromq.broker import ZeroMQComm
    import time
    import random
    import uuid
    from datetime import datetime, timezone

    async def _run_ingest():
        comms = ZeroMQComm()
        await comms.connect(bind_pub=False, bind_sub=False)
        router = EventRouter()
        
        console.print(f"[bold cyan]Ingestion started...[/bold cyan]")
        
        events_sent = 0
        
        if pcap:
            collector = PCAPCollector()
            console.print(f"Reading PCAP: [yellow]{pcap}[/yellow]")
            async for event in collector.stream_file(Path(pcap)):
                routed_agents = await router.route(event)
                for agent_type in routed_agents:
                    t = topic or f"events.{agent_type.value}"
                    await comms.publish(t, event.to_dict())
                events_sent += 1
                await asyncio.sleep(interval)
        
        elif sample:
            console.print(f"Generating [yellow]{count}[/yellow] sample [green]{sample}[/green] events")
            for _ in range(count):
                # Fake normalized event
                event_data = {
                    "id": f"EVT-{uuid.uuid4().hex[:6].upper()}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "simulation",
                    "event_type": sample,
                    "src_ip": f"192.168.1.{random.randint(2, 254)}",
                    "dst_ip": f"10.0.0.{random.randint(2, 254)}",
                    "payload_size": random.randint(64, 1500),
                }
                
                t = topic or f"events.{sample}"
                await comms.publish(t, event_data)
                events_sent += 1
                console.print(f"  [blue]→[/blue] Published to {t}")
                await asyncio.sleep(interval)
        
        else:
            console.print("[red]Specify --pcap FILE or --sample TYPE[/red]")
            return

        console.print(f"[bold green]Ingestion complete. Sent {events_sent} events.[/bold green]")
        await comms.disconnect()

    asyncio.run(_run_ingest())


@cli.command()
def status():
    """Show system status."""
    table = Table(title="CDSI System Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")

    from config.settings import get_settings
    settings = get_settings()

    # Check datasets
    for agent_type in ["ddos", "anomaly", "malware", "phishing", "mitm", "ransomware"]:
        data_path = settings.dataset_processed_path / agent_type
        has_data = data_path.exists() and any(data_path.iterdir()) if data_path.exists() else False
        table.add_row(f"Dataset: {agent_type}", "v Ready" if has_data else "x Not found")

    # Check models
    for agent_type in ["ddos", "anomaly", "malware", "phishing", "mitm", "ransomware"]:
        model_path = settings.model_storage_path / agent_type / f"{agent_type}_model.pkl"
        table.add_row(f"Model: {agent_type}", "v Trained" if model_path.exists() else "x Not trained")

    console.print(table)


def _create_agent(agent_type: str):
    """Factory to create agent instances."""
    from agents.ddos.agent import DDoSAgent
    from agents.anomaly.agent import AnomalyAgent
    from agents.malware.agent import MalwareAgent
    from agents.phishing.agent import PhishingAgent
    from agents.mitm.agent import MITMAgent
    from agents.ransomware.agent import RansomwareAgent

    agents = {
        "ddos": DDoSAgent,
        "anomaly": AnomalyAgent,
        "malware": MalwareAgent,
        "phishing": PhishingAgent,
        "mitm": MITMAgent,
        "ransomware": RansomwareAgent,
    }

    cls = agents.get(agent_type)
    if not cls:
        raise ValueError(f"Unknown agent type: {agent_type}")
    return cls()


if __name__ == "__main__":
    cli()
