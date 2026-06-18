from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts.experiments.recalcular_dataset_desde_ide import generar_wide


INPUT_PATH = "backend/data/dataset_clasificacion_multiclase_temporal.csv"
OUTPUT_PATH = "backend/data/dataset_clasificacion_multiclase_wide.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convierte dataset temporal multiclase a una fila por parcela."
    )
    parser.add_argument("--input", default=INPUT_PATH)
    parser.add_argument("--output", default=OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)
    df["parcela_id"] = df["parcela_id"].astype(str)
    wide = generar_wide(df)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(output, index=False)
    print("Input:", args.input, df.shape)
    print("Output:", output, wide.shape)
    print("Distribucion:", wide["cultivo"].value_counts().to_dict())


if __name__ == "__main__":
    main()
