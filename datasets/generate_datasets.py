"""
CDSI Synthetic Dataset Generator

Generates realistic synthetic CSV datasets for all 6 agents when real datasets
are unavailable. Each dataset matches the agent's expected feature schema with
realistic value distributions for benign vs attack classes.
"""
import numpy as np
import pandas as pd
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings

# ── Feature definitions per agent ─────────────────────────────────────────

DDOS_FEATURES = [
    "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
    "Total Length of Fwd Packets", "Total Length of Bwd Packets",
    "Fwd Packet Length Max", "Fwd Packet Length Min", "Fwd Packet Length Mean",
    "Bwd Packet Length Max", "Bwd Packet Length Min", "Bwd Packet Length Mean",
    "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std",
    "Flow IAT Max", "Flow IAT Min", "Fwd IAT Total", "Fwd IAT Mean",
    "Fwd IAT Std", "Fwd IAT Max", "Fwd IAT Min", "Bwd IAT Total",
    "Bwd IAT Mean", "Bwd IAT Std", "Bwd IAT Max", "Bwd IAT Min",
    "Fwd PSH Flags", "Bwd PSH Flags", "Fwd URG Flags", "Bwd URG Flags",
    "Fwd Packets/s", "Bwd Packets/s", "Packet Length Min", "Packet Length Max",
    "Packet Length Mean", "Packet Length Std", "Packet Length Variance",
    "SYN Flag Count", "RST Flag Count", "PSH Flag Count", "ACK Flag Count",
    "URG Flag Count", "Average Packet Size", "Avg Fwd Segment Size",
    "Avg Bwd Segment Size", "Init_Win_bytes_forward", "Init_Win_bytes_backward",
    "Active Mean", "Active Std", "Idle Mean", "Idle Std",
]

ANOMALY_FEATURES = [
    "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
    "Total Length of Fwd Packets", "Total Length of Bwd Packets",
    "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std",
    "Fwd IAT Mean", "Bwd IAT Mean", "Packet Length Mean",
    "Packet Length Std", "Average Packet Size", "SYN Flag Count",
    "RST Flag Count", "ACK Flag Count", "Init_Win_bytes_forward",
    "Init_Win_bytes_backward", "Active Mean", "Idle Mean",
]

MALWARE_FEATURES = [
    "size", "vsize", "has_debug", "has_relocations", "has_resources",
    "has_signature", "has_tls", "symbols", "sections", "imports",
    "exports", "entry_point", "strings_count", "avg_string_length",
    "max_string_length", "pe_header_size", "optional_header_size",
    "code_section_size", "data_section_size", "entropy_mean",
    "entropy_max", "entropy_min", "api_count", "suspicious_api_count",
    "dll_count", "file_alignment", "section_alignment",
    "linker_version_major", "linker_version_minor", "os_version",
]

PHISHING_FEATURES = [
    "url_length", "hostname_length", "path_length", "num_dots",
    "num_hyphens", "num_underscores", "num_slashes", "num_questionmarks",
    "num_ats", "num_equals", "num_ampersands", "num_digits",
    "num_subdomains", "has_ip", "has_https", "has_port",
    "path_depth", "domain_entropy", "tld_length", "has_suspicious_tld",
    "num_special_chars", "has_login_keyword", "has_secure_keyword",
    "has_update_keyword", "has_bank_keyword", "digit_ratio",
    "letter_ratio", "is_shortened", "domain_age_proxy",
    "alexa_rank_proxy",
]

MITM_FEATURES = [
    "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
    "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std",
    "Fwd IAT Mean", "Bwd IAT Mean", "Packet Length Mean",
    "Packet Length Std", "Average Packet Size", "SYN Flag Count",
    "RST Flag Count", "ACK Flag Count", "Init_Win_bytes_forward",
    "Init_Win_bytes_backward", "Active Mean", "Idle Mean",
    "Fwd Packet Length Mean", "Bwd Packet Length Mean",
]

RANSOMWARE_FEATURES = [
    "file_entropy", "entropy_delta", "api_call_count", "suspicious_api_ratio",
    "file_ops_per_second", "unique_extensions_modified", "encryption_api_calls",
    "network_connections", "dns_queries", "registry_modifications",
    "process_injections", "privilege_escalation_attempts", "shadow_copy_deletion",
    "file_rename_count", "write_byte_rate", "read_write_ratio",
    "mutex_creation", "service_modifications", "boot_persistence",
    "flow_duration", "total_fwd_packets", "total_bwd_packets",
    "flow_bytes_per_s", "flow_packets_per_s", "packet_length_mean",
    "avg_packet_size", "syn_flag_count", "rst_flag_count",
]

# ── Generator functions ───────────────────────────────────────────────────

def generate_network_flow_data(n_samples: int, features: list, rng: np.random.Generator) -> pd.DataFrame:
    """Generate synthetic network flow data (DDoS, Anomaly, MITM)."""
    n_benign = int(n_samples * 0.7)
    n_attack = n_samples - n_benign

    data = {}
    for feat in features:
        if "Duration" in feat:
            benign = rng.exponential(50000, n_benign)
            attack = rng.exponential(5000, n_attack)
        elif "Packets" in feat and "Total" in feat:
            benign = rng.poisson(15, n_benign).astype(float)
            attack = rng.poisson(500, n_attack).astype(float)
        elif "Length" in feat and ("Total" in feat or "Max" in feat):
            benign = rng.exponential(300, n_benign)
            attack = rng.exponential(50, n_attack)
        elif "Length" in feat and ("Min" in feat or "Mean" in feat):
            benign = rng.exponential(100, n_benign)
            attack = rng.exponential(20, n_attack)
        elif "Bytes/s" in feat or "bytes_per_s" in feat:
            benign = rng.exponential(5000, n_benign)
            attack = rng.exponential(500000, n_attack)
        elif "Packets/s" in feat or "packets_per_s" in feat:
            benign = rng.exponential(20, n_benign)
            attack = rng.exponential(2000, n_attack)
        elif "IAT" in feat:
            benign = rng.exponential(10000, n_benign)
            attack = rng.exponential(100, n_attack)
        elif "Flag" in feat or "flag" in feat:
            benign = rng.poisson(1, n_benign).astype(float)
            attack = rng.poisson(20, n_attack).astype(float)
        elif "Win_bytes" in feat or "Segment" in feat:
            benign = rng.normal(8192, 2000, n_benign)
            attack = rng.normal(512, 200, n_attack)
        elif "Active" in feat or "Idle" in feat:
            benign = rng.exponential(5000, n_benign)
            attack = rng.exponential(100, n_attack)
        elif "Variance" in feat:
            benign = rng.exponential(500, n_benign)
            attack = rng.exponential(10, n_attack)
        elif "Average" in feat or "Avg" in feat:
            benign = rng.exponential(200, n_benign)
            attack = rng.exponential(40, n_attack)
        elif "PSH" in feat or "URG" in feat:
            benign = rng.binomial(1, 0.1, n_benign).astype(float)
            attack = rng.binomial(1, 0.8, n_attack).astype(float)
        else:
            benign = rng.normal(50, 20, n_benign)
            attack = rng.normal(200, 50, n_attack)

        data[feat] = np.abs(np.concatenate([benign, attack]))

    labels = np.concatenate([np.zeros(n_benign), np.ones(n_attack)])
    data["Label"] = labels.astype(int)

    df = pd.DataFrame(data)
    return df.sample(frac=1, random_state=42).reset_index(drop=True)


def generate_malware_data(n_samples: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate synthetic PE file feature data."""
    n_benign = int(n_samples * 0.7)
    n_attack = n_samples - n_benign
    data = {}

    for feat in MALWARE_FEATURES:
        if feat == "size":
            benign = rng.lognormal(12, 1.5, n_benign)
            attack = rng.lognormal(10, 2, n_attack)
        elif feat == "vsize":
            benign = rng.lognormal(11, 1.5, n_benign)
            attack = rng.lognormal(9, 2, n_attack)
        elif feat.startswith("has_"):
            benign = rng.binomial(1, 0.7, n_benign).astype(float)
            attack = rng.binomial(1, 0.2, n_attack).astype(float)
        elif feat in ("symbols", "sections", "imports", "exports"):
            benign = rng.poisson(20 if feat != "exports" else 5, n_benign).astype(float)
            attack = rng.poisson(5 if feat != "exports" else 1, n_attack).astype(float)
        elif "entropy" in feat:
            benign = rng.normal(4.5, 0.8, n_benign)
            attack = rng.normal(7.2, 0.5, n_attack)
        elif "api_count" in feat:
            benign = rng.poisson(80, n_benign).astype(float)
            attack = rng.poisson(30, n_attack).astype(float)
        elif "suspicious_api_count" in feat:
            benign = rng.poisson(2, n_benign).astype(float)
            attack = rng.poisson(15, n_attack).astype(float)
        elif "dll_count" in feat:
            benign = rng.poisson(8, n_benign).astype(float)
            attack = rng.poisson(3, n_attack).astype(float)
        elif "strings" in feat:
            benign = rng.poisson(200, n_benign).astype(float)
            attack = rng.poisson(50, n_attack).astype(float)
        elif "version" in feat or "os_version" in feat:
            benign = rng.choice([6, 7, 8, 10], n_benign).astype(float)
            attack = rng.choice([5, 6], n_attack).astype(float)
        elif "alignment" in feat:
            benign = rng.choice([512, 1024, 4096], n_benign).astype(float)
            attack = rng.choice([200, 512], n_attack).astype(float)
        elif "header" in feat or "section_size" in feat:
            benign = rng.lognormal(8, 1, n_benign)
            attack = rng.lognormal(6, 2, n_attack)
        elif "entry_point" in feat:
            benign = rng.lognormal(10, 1, n_benign)
            attack = rng.lognormal(8, 2, n_attack)
        else:
            benign = rng.normal(50, 15, n_benign)
            attack = rng.normal(20, 10, n_attack)

        data[feat] = np.abs(np.concatenate([benign, attack]))

    data["Label"] = np.concatenate([np.zeros(n_benign), np.ones(n_attack)]).astype(int)
    df = pd.DataFrame(data)
    return df.sample(frac=1, random_state=42).reset_index(drop=True)


def generate_phishing_data(n_samples: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate synthetic URL feature data."""
    n_benign = int(n_samples * 0.7)
    n_attack = n_samples - n_benign
    data = {}

    for feat in PHISHING_FEATURES:
        if "length" in feat:
            benign = rng.normal(30, 10, n_benign)
            attack = rng.normal(80, 25, n_attack)
        elif "num_" in feat and feat != "num_subdomains":
            benign = rng.poisson(2, n_benign).astype(float)
            attack = rng.poisson(8, n_attack).astype(float)
        elif "num_subdomains" in feat:
            benign = rng.poisson(1, n_benign).astype(float)
            attack = rng.poisson(4, n_attack).astype(float)
        elif feat.startswith("has_") and feat != "has_https":
            benign = rng.binomial(1, 0.05, n_benign).astype(float)
            attack = rng.binomial(1, 0.6, n_attack).astype(float)
        elif feat == "has_https":
            benign = rng.binomial(1, 0.85, n_benign).astype(float)
            attack = rng.binomial(1, 0.3, n_attack).astype(float)
        elif "ratio" in feat:
            benign = rng.beta(7, 3, n_benign)
            attack = rng.beta(3, 7, n_attack)
        elif "entropy" in feat:
            benign = rng.normal(3.0, 0.5, n_benign)
            attack = rng.normal(4.5, 0.3, n_attack)
        elif "depth" in feat:
            benign = rng.poisson(2, n_benign).astype(float)
            attack = rng.poisson(5, n_attack).astype(float)
        elif "proxy" in feat:
            benign = rng.exponential(500, n_benign)
            attack = rng.exponential(50, n_attack)
        elif "is_shortened" in feat:
            benign = rng.binomial(1, 0.02, n_benign).astype(float)
            attack = rng.binomial(1, 0.3, n_attack).astype(float)
        else:
            benign = rng.normal(10, 5, n_benign)
            attack = rng.normal(30, 10, n_attack)

        data[feat] = np.abs(np.concatenate([benign, attack]))

    data["Label"] = np.concatenate([np.zeros(n_benign), np.ones(n_attack)]).astype(int)
    df = pd.DataFrame(data)
    return df.sample(frac=1, random_state=42).reset_index(drop=True)


def generate_ransomware_data(n_samples: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate synthetic ransomware behavioral data."""
    n_benign = int(n_samples * 0.7)
    n_attack = n_samples - n_benign
    data = {}

    for feat in RANSOMWARE_FEATURES:
        if "entropy" in feat and "delta" not in feat:
            benign = rng.normal(4.0, 1.0, n_benign)
            attack = rng.normal(7.8, 0.3, n_attack)
        elif "entropy_delta" in feat:
            benign = rng.normal(0.1, 0.05, n_benign)
            attack = rng.normal(3.5, 0.5, n_attack)
        elif "api_call_count" in feat:
            benign = rng.poisson(50, n_benign).astype(float)
            attack = rng.poisson(300, n_attack).astype(float)
        elif "suspicious_api_ratio" in feat:
            benign = rng.beta(1, 20, n_benign)
            attack = rng.beta(10, 5, n_attack)
        elif "file_ops_per_second" in feat:
            benign = rng.exponential(5, n_benign)
            attack = rng.exponential(200, n_attack)
        elif "unique_extensions" in feat:
            benign = rng.poisson(3, n_benign).astype(float)
            attack = rng.poisson(25, n_attack).astype(float)
        elif "encryption_api" in feat:
            benign = rng.poisson(1, n_benign).astype(float)
            attack = rng.poisson(50, n_attack).astype(float)
        elif "shadow_copy" in feat:
            benign = np.zeros(n_benign)
            attack = rng.binomial(1, 0.85, n_attack).astype(float)
        elif "file_rename" in feat:
            benign = rng.poisson(2, n_benign).astype(float)
            attack = rng.poisson(100, n_attack).astype(float)
        elif "write_byte_rate" in feat:
            benign = rng.exponential(1000, n_benign)
            attack = rng.exponential(500000, n_attack)
        elif "read_write_ratio" in feat:
            benign = rng.beta(5, 5, n_benign)
            attack = rng.beta(1, 10, n_attack)
        elif "mutex" in feat or "boot_persistence" in feat or "service_modifications" in feat:
            benign = rng.binomial(1, 0.05, n_benign).astype(float)
            attack = rng.binomial(1, 0.8, n_attack).astype(float)
        elif "process_injections" in feat or "privilege_escalation" in feat:
            benign = rng.poisson(0, n_benign).astype(float)
            attack = rng.poisson(5, n_attack).astype(float)
        elif "network_connections" in feat or "dns_queries" in feat or "registry_modifications" in feat:
            benign = rng.poisson(5, n_benign).astype(float)
            attack = rng.poisson(50, n_attack).astype(float)
        elif "flow_duration" in feat:
            benign = rng.exponential(50000, n_benign)
            attack = rng.exponential(5000, n_attack)
        elif "packets" in feat:
            benign = rng.poisson(15, n_benign).astype(float)
            attack = rng.poisson(200, n_attack).astype(float)
        elif "bytes_per_s" in feat or "packets_per_s" in feat:
            benign = rng.exponential(5000, n_benign)
            attack = rng.exponential(200000, n_attack)
        elif "flag" in feat:
            benign = rng.poisson(1, n_benign).astype(float)
            attack = rng.poisson(15, n_attack).astype(float)
        elif "packet_length" in feat or "avg_packet" in feat:
            benign = rng.exponential(200, n_benign)
            attack = rng.exponential(50, n_attack)
        else:
            benign = rng.normal(10, 5, n_benign)
            attack = rng.normal(50, 15, n_attack)

        data[feat] = np.abs(np.concatenate([benign, attack]))

    data["Label"] = np.concatenate([np.zeros(n_benign), np.ones(n_attack)]).astype(int)
    df = pd.DataFrame(data)
    return df.sample(frac=1, random_state=42).reset_index(drop=True)


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    settings = get_settings()
    rng = np.random.default_rng(42)
    n_samples = 5000

    generators = {
        "ddos":       lambda: generate_network_flow_data(n_samples, DDOS_FEATURES, rng),
        "anomaly":    lambda: generate_network_flow_data(n_samples, ANOMALY_FEATURES, rng),
        "malware":    lambda: generate_malware_data(n_samples, rng),
        "phishing":   lambda: generate_phishing_data(n_samples, rng),
        "mitm":       lambda: generate_network_flow_data(n_samples, MITM_FEATURES, rng),
        "ransomware": lambda: generate_ransomware_data(n_samples, rng),
    }

    for agent_type, gen_func in generators.items():
        print(f"\n[+] Generating {agent_type} dataset ({n_samples} samples)...")
        df = gen_func()

        # Save to raw directory
        raw_dir = settings.dataset_raw_path / agent_type
        raw_dir.mkdir(parents=True, exist_ok=True)
        csv_path = raw_dir / f"{agent_type}_synthetic.csv"
        df.to_csv(csv_path, index=False)
        print(f"    ✓ Saved to {csv_path}")
        print(f"    Features: {len(df.columns) - 1}, Benign: {(df['Label']==0).sum()}, Attack: {(df['Label']==1).sum()}")

    print("\n[✓] All datasets generated successfully!")
    print("    Next: python cli.py preprocess --all")
    print("    Then: python cli.py train --all")


if __name__ == "__main__":
    main()
