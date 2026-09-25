"""
CDSI Central Configuration — Pydantic Settings loaded from .env
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Central settings for all CDSI services."""

    # ── Server ──
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    use_simulation: bool = False
    debug: bool = False
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    use_kafka: bool = False

    # ── API Keys ──
    phishtank_api_key: str = ""
    malwarebazaar_api_key: str = ""
    virustotal_api_key: str = ""

    # ── Kafka ──
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_threats: str = "cdsi.threats"
    kafka_topic_consensus: str = "cdsi.consensus"
    kafka_topic_telemetry: str = "cdsi.telemetry"

    # ── ZeroMQ ──
    zmq_host: str = "127.0.0.1"
    zmq_port: int = 5555
    zmq_pub_address: str = "tcp://127.0.0.1:5555"
    zmq_sub_address: str = "tcp://127.0.0.1:5555"

    # ── gRPC ──
    grpc_server_address: str = "0.0.0.0:50051"
    grpc_use_tls: bool = False
    grpc_cert_path: str = "certs/server.crt"
    grpc_key_path: str = "certs/server.key"

    # ── Wazuh ──
    wazuh_api_url: str = "https://localhost:55000"
    wazuh_api_user: str = "wazuh"
    wazuh_api_password: str = "wazuh"

    # ── Database ──
    database_url: str = f"sqlite:///{BASE_DIR / 'cdsi.db'}"

    # ── Security ──
    jwt_secret_key: str = "change-this-to-a-secure-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # ── Paths ──
    model_storage_path: Path = BASE_DIR / "models"
    dataset_storage_path: Path = BASE_DIR / "datasets"
    dataset_raw_path: Path = BASE_DIR / "datasets" / "raw"
    dataset_processed_path: Path = BASE_DIR / "datasets" / "processed"

    # ── Consensus ──
    consensus_threshold: float = 0.66
    consensus_timeout_ms: int = 5000

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def ensure_directories(self) -> None:
        """Create required directories if they do not exist."""
        for p in [
            self.model_storage_path,
            self.dataset_storage_path,
            self.dataset_raw_path,
            self.dataset_processed_path,
        ]:
            p.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    settings = Settings()
    settings.ensure_directories()
    return settings
