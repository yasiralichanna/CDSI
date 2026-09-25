"""
CDSI Dataset Preprocessor

Normalizes, encodes, scales, and splits datasets into ML-ready format.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sklearn.preprocessing import StandardScaler, LabelEncoder, MinMaxScaler
from sklearn.model_selection import train_test_split
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class DatasetPreprocessor:
    """
    Shared preprocessing utilities for all agent datasets.
    Handles normalization, encoding, scaling, and splitting.
    """

    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        settings = get_settings()
        self._raw_dir = settings.dataset_raw_path / agent_type
        self._processed_dir = settings.dataset_processed_path / agent_type
        self._processed_dir.mkdir(parents=True, exist_ok=True)

    def preprocess(
        self,
        input_path: Optional[Path] = None,
        label_column: str = "Label",
        test_size: float = 0.2,
        val_size: float = 0.1,
    ) -> Dict[str, Path]:
        """
        Full preprocessing pipeline:
          1. Load raw data
          2. Clean (drop NaN, inf, duplicates)
          3. Encode categorical variables
          4. Scale numerical features
          5. Split train/validation/test
          6. Save to processed directory

        Returns dict of output file paths.
        """
        # Find input file
        if input_path is None:
            input_path = self._find_raw_file()

        logger.info("preprocess.started", agent=self.agent_type, input=str(input_path))

        # Load
        df = self._load_data(input_path)
        logger.info("preprocess.loaded", rows=len(df), cols=len(df.columns))

        # Clean
        df = self._clean(df)

        # Separate features and labels
        if label_column not in df.columns:
            # Try common alternatives
            for alt in ["label", "Label", "class", "Class", "target", "Result"]:
                if alt in df.columns:
                    label_column = alt
                    break
            else:
                raise ValueError(f"Label column '{label_column}' not found. Available: {list(df.columns)}")

        y = df[label_column]
        X = df.drop(columns=[label_column])

        # Encode categorical features
        X, cat_encoders = self._encode_categoricals(X)

        # Scale numerical features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Encode labels
        label_encoder = LabelEncoder()
        y_encoded = label_encoder.fit_transform(y)

        # Split: train / validation / test
        X_train, X_temp, y_train, y_temp = train_test_split(
            X_scaled, y_encoded, test_size=test_size + val_size,
            random_state=42, stratify=y_encoded
        )

        relative_val = val_size / (test_size + val_size)
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, test_size=1 - relative_val,
            random_state=42, stratify=y_temp
        )

        # Save
        outputs = {
            "X": self._processed_dir / "X.npy",
            "y": self._processed_dir / "y.npy",
            "X_train": self._processed_dir / "X_train.npy",
            "y_train": self._processed_dir / "y_train.npy",
            "X_val": self._processed_dir / "X_val.npy",
            "y_val": self._processed_dir / "y_val.npy",
            "X_test": self._processed_dir / "X_test.npy",
            "y_test": self._processed_dir / "y_test.npy",
        }

        np.save(outputs["X"], X_scaled)
        np.save(outputs["y"], y_encoded)
        np.save(outputs["X_train"], X_train)
        np.save(outputs["y_train"], y_train)
        np.save(outputs["X_val"], X_val)
        np.save(outputs["y_val"], y_val)
        np.save(outputs["X_test"], X_test)
        np.save(outputs["y_test"], y_test)

        # Save processed CSV for inspection
        processed_csv = self._processed_dir / f"{self.agent_type}_processed.csv"
        result_df = pd.DataFrame(X_scaled, columns=X.columns)
        result_df[label_column] = y_encoded
        result_df.to_csv(processed_csv, index=False)
        outputs["csv"] = processed_csv

        # Save feature names
        feature_file = self._processed_dir / "features.txt"
        feature_file.write_text("\n".join(X.columns.tolist()))
        outputs["features"] = feature_file

        logger.info(
            "preprocess.complete",
            agent=self.agent_type,
            train=len(X_train), val=len(X_val), test=len(X_test),
        )
        return outputs

    def _load_data(self, path: Path) -> pd.DataFrame:
        """Load data from various formats."""
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path, low_memory=False)
        elif suffix == ".parquet":
            return pd.read_parquet(path)
        elif suffix == ".json":
            return pd.read_json(path)
        elif suffix == ".arff":
            return self._load_arff(path)
        else:
            return pd.read_csv(path, low_memory=False)

    def _load_arff(self, path: Path) -> pd.DataFrame:
        """Load ARFF format (used by UCI datasets)."""
        from scipy.io import arff
        data, meta = arff.loadarff(path)
        df = pd.DataFrame(data)
        # Decode byte strings
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].str.decode("utf-8", errors="ignore")
        return df

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean dataset: handle NaN, inf, duplicates."""
        initial = len(df)

        # Replace inf with NaN
        df = df.replace([np.inf, -np.inf], np.nan)

        # Drop rows with NaN
        df = df.dropna()

        # Drop duplicates
        df = df.drop_duplicates()

        # Remove columns with zero variance
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        zero_var = [c for c in numeric_cols if df[c].std() == 0]
        if zero_var:
            df = df.drop(columns=zero_var)

        logger.info(
            "preprocess.cleaned",
            initial=initial,
            final=len(df),
            dropped=initial - len(df),
            zero_var_cols=len(zero_var),
        )
        return df

    def _encode_categoricals(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """Encode categorical variables using LabelEncoder."""
        encoders = {}
        cat_cols = df.select_dtypes(include=["object", "category"]).columns

        for col in cat_cols:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            encoders[col] = le

        return df, encoders

    def _find_raw_file(self) -> Path:
        """Find the first data file in the raw directory."""
        for ext in [".csv", ".parquet", ".json", ".arff"]:
            files = list(self._raw_dir.glob(f"*{ext}"))
            if files:
                return files[0]
        raise FileNotFoundError(f"No data files found in {self._raw_dir}")
