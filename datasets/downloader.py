"""
CDSI Dataset Downloader

Automatically downloads real cybersecurity datasets for each agent.
Supports APIs with authentication, rate limiting, and caching.
"""
from __future__ import annotations

import hashlib
import os
import time
import zipfile
import gzip
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)

# ── Dataset registry ──────────────────────────────────────────────────────
DATASETS = {
    "ddos": {
        "name": "CIC-DDoS2019",
        "urls": [
            "https://data.mendeley.com/public-files/datasets/ssnc74xm6r/files/01onal-CIC-DDoS2019.csv",
        ],
        "description": "Canadian Institute for Cybersecurity DDoS 2019 dataset",
        "format": "csv",
    },
    "anomaly": {
        "name": "CICIDS2017",
        "urls": [
            "https://data.mendeley.com/public-files/datasets/jxkj7wsh6p/files/cicids2017.csv",
        ],
        "description": "CICIDS2017 intrusion detection dataset",
        "format": "csv",
    },
    "malware": {
        "name": "EMBER",
        "urls": [
            "https://ember.elastic.co/ember_dataset_2018_2.tar.bz2",
        ],
        "description": "EMBER PE malware dataset",
        "format": "tar.bz2",
        "api": {
            "name": "MalwareBazaar",
            "endpoint": "https://mb-api.abuse.ch/api/v1/",
            "auth_env": "MALWAREBAZAAR_API_KEY",
        },
    },
    "phishing": {
        "name": "PhishTank + UCI",
        "urls": [
            "https://archive.ics.uci.edu/ml/machine-learning-databases/00327/Training%20Dataset.arff",
        ],
        "description": "PhishTank + UCI phishing URL dataset",
        "format": "arff",
        "api": {
            "name": "PhishTank",
            "endpoint": "https://data.phishtank.com/data/online-valid.json",
            "auth_env": "PHISHTANK_API_KEY",
            "rate_limit_per_minute": 10,
        },
    },
    "mitm": {
        "name": "CICIDS2017-MITM",
        "urls": [
            "https://data.mendeley.com/public-files/datasets/jxkj7wsh6p/files/cicids2017_arp_dns.csv",
        ],
        "description": "CICIDS2017 ARP/DNS poisoning subset",
        "format": "csv",
    },
    "ransomware": {
        "name": "CTU-13 + BIG2015",
        "urls": [
            "https://mcfp.weebly.com/uploads/5/0/0/2/50029787/ctu-13-dataset.tar.gz",
        ],
        "description": "CTU-13 botnet + BIG 2015 malware dataset",
        "format": "tar.gz",
    },
}


class DatasetDownloader:
    """
    Downloads and caches cybersecurity datasets.
    Supports URL downloads and API-based collection.
    """

    def __init__(self):
        settings = get_settings()
        self._raw_dir = settings.dataset_raw_path
        self._processed_dir = settings.dataset_processed_path
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        self._rate_limits: Dict[str, float] = {}

    def download_dataset(self, agent_type: str, force: bool = False) -> Path:
        """
        Download dataset for a specific agent type.
        Returns path to the downloaded data directory.
        """
        config = DATASETS.get(agent_type)
        if not config:
            raise ValueError(f"Unknown agent type: {agent_type}")

        dest_dir = self._raw_dir / agent_type
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Check if already downloaded
        if not force and self._is_downloaded(dest_dir):
            logger.info("dataset.already_exists", agent=agent_type, path=str(dest_dir))
            return dest_dir

        logger.info("dataset.downloading", agent=agent_type, name=config["name"])

        # Download from URLs
        for url in config.get("urls", []):
            try:
                self._download_file(url, dest_dir)
            except Exception as e:
                logger.warning("dataset.download_failed", url=url, error=str(e))

        # Download from API if available
        api_config = config.get("api")
        if api_config:
            try:
                self._download_from_api(api_config, dest_dir)
            except Exception as e:
                logger.warning("dataset.api_failed", api=api_config["name"], error=str(e))

        return dest_dir

    def download_all(self, force: bool = False) -> Dict[str, Path]:
        """Download all datasets."""
        results = {}
        for agent_type in DATASETS:
            try:
                results[agent_type] = self.download_dataset(agent_type, force)
            except Exception as e:
                logger.error("dataset.download_error", agent=agent_type, error=str(e))
        return results

    def _download_file(self, url: str, dest_dir: Path) -> Path:
        """Download a file from URL with progress."""
        filename = url.split("/")[-1].split("?")[0]
        if not filename:
            filename = hashlib.md5(url.encode()).hexdigest()

        dest_path = dest_dir / filename

        if dest_path.exists():
            logger.info("dataset.file_exists", path=str(dest_path))
            return dest_path

        logger.info("dataset.downloading_file", url=url[:80])

        with httpx.Client(timeout=600, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))
                downloaded = 0

                with open(dest_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)

        # Extract if compressed
        if filename.endswith(".zip"):
            self._extract_zip(dest_path, dest_dir)
        elif filename.endswith(".tar.gz") or filename.endswith(".tgz"):
            self._extract_tar(dest_path, dest_dir)
        elif filename.endswith(".gz") and not filename.endswith(".tar.gz"):
            self._extract_gzip(dest_path, dest_dir)

        logger.info("dataset.downloaded", path=str(dest_path), size_mb=dest_path.stat().st_size / 1e6)
        return dest_path

    def _download_from_api(self, api_config: Dict, dest_dir: Path) -> None:
        """Download data from an API endpoint."""
        settings = get_settings()
        api_key = getattr(settings, api_config.get("auth_env", "").lower(), "")

        # Rate limiting
        rate_limit = api_config.get("rate_limit_per_minute", 60)
        api_name = api_config["name"]
        last_call = self._rate_limits.get(api_name, 0)
        wait = max(0, (60 / rate_limit) - (time.time() - last_call))
        if wait > 0:
            time.sleep(wait)

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        with httpx.Client(timeout=120) as client:
            response = client.get(
                api_config["endpoint"],
                headers=headers,
            )
            response.raise_for_status()

            dest_file = dest_dir / f"{api_name.lower()}_data.json"
            dest_file.write_bytes(response.content)

        self._rate_limits[api_name] = time.time()
        logger.info("dataset.api_downloaded", api=api_name)

    def _is_downloaded(self, dest_dir: Path) -> bool:
        """Check if dataset directory has any data files."""
        return any(
            f.suffix in {".csv", ".json", ".arff", ".npy", ".parquet"}
            for f in dest_dir.iterdir()
            if f.is_file()
        )

    def _extract_zip(self, path: Path, dest: Path) -> None:
        with zipfile.ZipFile(path, "r") as z:
            z.extractall(dest)

    def _extract_tar(self, path: Path, dest: Path) -> None:
        import tarfile
        with tarfile.open(path, "r:*") as t:
            t.extractall(dest)

    def _extract_gzip(self, path: Path, dest: Path) -> None:
        out_path = dest / path.stem
        with gzip.open(path, "rb") as f_in:
            with open(out_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
