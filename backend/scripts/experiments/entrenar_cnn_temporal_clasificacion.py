from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_class_weight

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts.experiments.entrenar_clasificador_tensorflow import to_jsonable


INPUT_PATH = "backend/data/dataset_clasificacion_multiclase_temporal.csv"
OUTPUT_DIR = Path("backend/models/clasificador_tensorflow/cnn_temporal_multiclase")
TARGET_CLASSES = ["vid", "olivo", "frutales", "incultos", "anuales"]
RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Entrena una CNN 1D temporal para clasificacion multiclase por parcela. "
            "Consume observaciones Sentinel-2 temporales y arma X=(parcelas, fechas, features)."
        )
    )
    parser.add_argument("--input", default=INPUT_PATH)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--target", default="cultivo")
    parser.add_argument("--id-col", default="parcela_id")
    parser.add_argument("--date-col", default="fecha")
    parser.add_argument("--classes", nargs="+", default=TARGET_CLASSES)
    parser.add_argument(
        "--feature-set",
        choices=["mean", "mean-std", "all-spectral"],
        default="mean-std",
    )
    parser.add_argument("--include-time-features", action="store_true")
    parser.add_argument("--min-timesteps", type=int, default=3)
    parser.add_argument("--max-timesteps", type=int, default=None)
    parser.add_argument("--test-size", type=float, default=0.20)
    parser.add_argument("--validation-size", type=float, default=0.15)
    parser.add_argument("--epochs", type=int, default=140)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=8e-4)
    parser.add_argument("--dropout", type=float, default=0.35)
    parser.add_argument("--filters", nargs="+", type=int, default=[64, 128])
    parser.add_argument("--dense-units", type=int, default=64)
    parser.add_argument("--l2", type=float, default=1e-3)
    parser.add_argument("--random-state", type=int, default=RANDOM_STATE)
    return parser.parse_args()


def import_tensorflow():
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
    try:
        import tensorflow as tf
    except ImportError as exc:
        raise RuntimeError(
            "TensorFlow no esta instalado. Instalar con: "
            "venv/bin/pip install -r requirements-tensorflow.txt"
        ) from exc
    return tf


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    if "month" in result.columns:
        month = pd.to_numeric(result["month"], errors="coerce")
        result["month_sin"] = np.sin(2 * np.pi * month / 12)
        result["month_cos"] = np.cos(2 * np.pi * month / 12)
    if "day_of_year" in result.columns:
        day = pd.to_numeric(result["day_of_year"], errors="coerce")
        result["doy_sin"] = np.sin(2 * np.pi * day / 365.25)
        result["doy_cos"] = np.cos(2 * np.pi * day / 365.25)
    return result


def temporal_feature_columns(
    df: pd.DataFrame,
    target: str,
    id_col: str,
    date_col: str,
    feature_set: str,
    include_time_features: bool = False,
) -> list[str]:
    excluded = {
        target,
        id_col,
        date_col,
        "fecha_fin",
        "year",
        "month",
        "day_of_year",
        "window_days",
        "area_m2",
    }
    excluded_prefixes = ("scl_",)
    time_features = {"month_sin", "month_cos", "doy_sin", "doy_cos"}
    numeric_cols = list(df.select_dtypes(include=[np.number]).columns)
    features: list[str] = []

    for col in numeric_cols:
        if col in excluded or col.startswith(excluded_prefixes):
            continue
        if col in time_features:
            if include_time_features:
                features.append(col)
            continue
        if col.endswith("_count"):
            continue
        if feature_set == "mean" and col.endswith("_mean"):
            features.append(col)
        elif feature_set == "mean-std" and col.endswith(("_mean", "_stddev")):
            features.append(col)
        elif feature_set == "all-spectral":
            features.append(col)

    return features


def parcel_labels(df: pd.DataFrame, id_col: str, target: str) -> pd.Series:
    labels = df.groupby(id_col)[target].agg(lambda values: values.mode().iloc[0])
    return labels.astype(str)


def build_temporal_sequences(
    df: pd.DataFrame,
    id_col: str,
    date_col: str,
    target: str,
    features: list[str],
    classes: list[str],
    min_timesteps: int,
    max_timesteps: int | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], list[str]]:
    work = df.copy()
    work[target] = work[target].astype(str).str.strip().str.lower()
    valid_classes = [item.lower() for item in classes]
    work = work[work[target].isin(valid_classes)].copy()
    work[date_col] = pd.to_datetime(work[date_col])
    work[id_col] = work[id_col].astype(str)

    counts = work.groupby(id_col)[date_col].nunique()
    valid_ids = counts[counts >= min_timesteps].index
    work = work[work[id_col].isin(valid_ids)].copy()
    if work.empty:
        raise RuntimeError("No hay parcelas con suficientes fechas para armar secuencias.")

    dates = sorted(work[date_col].dropna().unique())
    if max_timesteps is not None:
        dates = dates[:max_timesteps]
        work = work[work[date_col].isin(dates)].copy()

    labels = parcel_labels(work, id_col, target)
    parcel_ids = sorted(labels.index.astype(str).tolist())
    date_index = pd.DatetimeIndex(dates)

    sequences = []
    sequence_labels = []
    sequence_ids = []
    for parcela_id in parcel_ids:
        parcel = work[work[id_col] == parcela_id].copy()
        if parcel[date_col].nunique() < min_timesteps:
            continue
        parcel = (
            parcel.groupby(date_col)[features]
            .mean(numeric_only=True)
            .reindex(date_index)
        )
        sequences.append(parcel.to_numpy(dtype=float))
        sequence_labels.append(labels.loc[parcela_id])
        sequence_ids.append(parcela_id)

    if not sequences:
        raise RuntimeError("No se pudieron construir secuencias temporales.")

    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(sequence_labels)
    return (
        np.stack(sequences),
        y,
        np.array(sequence_ids),
        [pd.Timestamp(date).date().isoformat() for date in date_index],
        label_encoder.classes_.tolist(),
    )


def split_indices(
    y: np.ndarray,
    test_size: float,
    validation_size: float,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    indices = np.arange(len(y))
    train_val_idx, test_idx = train_test_split(
        indices,
        test_size=test_size,
        stratify=y,
        random_state=random_state,
    )
    relative_val_size = validation_size / max(1e-9, 1 - test_size)
    train_idx, val_idx = train_test_split(
        train_val_idx,
        test_size=relative_val_size,
        stratify=y[train_val_idx],
        random_state=random_state,
    )
    return train_idx, val_idx, test_idx


def fit_sequence_preprocessor(
    x_train: np.ndarray,
) -> tuple[np.ndarray, SimpleImputer, StandardScaler]:
    n_samples, n_timesteps, n_features = x_train.shape
    flat = x_train.reshape(-1, n_features)
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    transformed = scaler.fit_transform(imputer.fit_transform(flat))
    return transformed.reshape(n_samples, n_timesteps, n_features), imputer, scaler


def transform_sequences(
    x: np.ndarray,
    imputer: SimpleImputer,
    scaler: StandardScaler,
) -> np.ndarray:
    n_samples, n_timesteps, n_features = x.shape
    flat = x.reshape(-1, n_features)
    transformed = scaler.transform(imputer.transform(flat))
    return transformed.reshape(n_samples, n_timesteps, n_features)


def build_cnn_model(
    tf: Any,
    input_shape: tuple[int, int],
    n_classes: int,
    filters: list[int],
    dense_units: int,
    dropout: float,
    learning_rate: float,
    l2_value: float,
):
    inputs = tf.keras.Input(shape=input_shape, name="temporal_features")
    x = inputs
    kernel_size = 3 if input_shape[0] >= 3 else 2
    for units in filters:
        x = tf.keras.layers.Conv1D(
            units,
            kernel_size=kernel_size,
            padding="same",
            activation="relu",
            kernel_regularizer=tf.keras.regularizers.l2(l2_value),
        )(x)
        x = tf.keras.layers.BatchNormalization()(x)
        x = tf.keras.layers.Dropout(dropout)(x)
    x = tf.keras.layers.GlobalAveragePooling1D()(x)
    x = tf.keras.layers.Dense(
        dense_units,
        activation="relu",
        kernel_regularizer=tf.keras.regularizers.l2(l2_value),
    )(x)
    x = tf.keras.layers.Dropout(dropout)(x)
    outputs = tf.keras.layers.Dense(n_classes, activation="softmax", name="cultivo")(x)
    model = tf.keras.Model(inputs=inputs, outputs=outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def distribution(labels: np.ndarray, class_names: list[str]) -> dict[str, int]:
    counts = pd.Series(labels).value_counts().sort_index()
    return {class_names[int(idx)]: int(value) for idx, value in counts.items()}


def train(args: argparse.Namespace) -> dict[str, Any]:
    tf = import_tensorflow()
    tf.keras.utils.set_random_seed(args.random_state)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input)
    if args.include_time_features:
        df = add_time_features(df)
    features = temporal_feature_columns(
        df,
        target=args.target,
        id_col=args.id_col,
        date_col=args.date_col,
        feature_set=args.feature_set,
        include_time_features=args.include_time_features,
    )
    if not features:
        raise RuntimeError("No se detectaron features temporales para la CNN.")

    x, y, parcel_ids, dates, class_names = build_temporal_sequences(
        df,
        id_col=args.id_col,
        date_col=args.date_col,
        target=args.target,
        features=features,
        classes=args.classes,
        min_timesteps=args.min_timesteps,
        max_timesteps=args.max_timesteps,
    )
    train_idx, val_idx, test_idx = split_indices(
        y,
        args.test_size,
        args.validation_size,
        args.random_state,
    )

    x_train, imputer, scaler = fit_sequence_preprocessor(x[train_idx])
    x_val = transform_sequences(x[val_idx], imputer, scaler)
    x_test = transform_sequences(x[test_idx], imputer, scaler)
    y_train = y[train_idx]
    y_val = y[val_idx]
    y_test = y[test_idx]

    class_weights_raw = compute_class_weight(
        class_weight="balanced",
        classes=np.unique(y_train),
        y=y_train,
    )
    class_weight = {
        int(label): float(weight)
        for label, weight in zip(np.unique(y_train), class_weights_raw)
    }

    model = build_cnn_model(
        tf=tf,
        input_shape=(x_train.shape[1], x_train.shape[2]),
        n_classes=len(class_names),
        filters=args.filters,
        dense_units=args.dense_units,
        dropout=args.dropout,
        learning_rate=args.learning_rate,
        l2_value=args.l2,
    )
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=args.patience,
            restore_best_weights=True,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            patience=max(5, args.patience // 2),
            factor=0.5,
            min_lr=1e-5,
        ),
    ]

    history = model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val),
        epochs=args.epochs,
        batch_size=args.batch_size,
        class_weight=class_weight,
        callbacks=callbacks,
        verbose=2,
    )

    probabilities = model.predict(x_test, batch_size=args.batch_size, verbose=0)
    y_pred = probabilities.argmax(axis=1)
    report = classification_report(
        y_test,
        y_pred,
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "macro_f1": float(f1_score(y_test, y_pred, average="macro")),
        "weighted_f1": float(f1_score(y_test, y_pred, average="weighted")),
        "epochs_trained": int(len(history.history.get("loss", []))),
    }

    model_path = output_dir / "cnn_temporal_clasificador.keras"
    preprocess_path = output_dir / "preprocesamiento_cnn_temporal.joblib"
    metrics_path = output_dir / "metricas_cnn_temporal.json"
    report_path = output_dir / "classification_report.csv"
    confusion_path = output_dir / "confusion_matrix.csv"
    history_path = output_dir / "history.csv"

    model.save(model_path)
    joblib.dump(
        {
            "imputer": imputer,
            "scaler": scaler,
            "features": features,
            "dates": dates,
            "class_names": class_names,
            "target": args.target,
            "id_col": args.id_col,
            "date_col": args.date_col,
        },
        preprocess_path,
    )
    pd.DataFrame(report).T.to_csv(report_path)
    pd.DataFrame(
        confusion_matrix(y_test, y_pred),
        index=class_names,
        columns=class_names,
    ).to_csv(confusion_path)
    pd.DataFrame(history.history).to_csv(history_path, index=False)

    metadata = {
        "input": args.input,
        "target": args.target,
        "classes": class_names,
        "features": features,
        "feature_set": args.feature_set,
        "dates": dates,
        "n_parcels": int(len(x)),
        "n_timesteps": int(x.shape[1]),
        "n_features": int(x.shape[2]),
        "n_train": int(len(train_idx)),
        "n_validation": int(len(val_idx)),
        "n_test": int(len(test_idx)),
        "distribution_total": distribution(y, class_names),
        "distribution_train": distribution(y_train, class_names),
        "distribution_validation": distribution(y_val, class_names),
        "distribution_test": distribution(y_test, class_names),
        "class_weight": class_weight,
        "filters": args.filters,
        "dense_units": args.dense_units,
        "dropout": args.dropout,
        "learning_rate": args.learning_rate,
        "l2": args.l2,
        "model_path": str(model_path),
        "preprocess_path": str(preprocess_path),
        "metrics": metrics,
        "test_parcela_ids": parcel_ids[test_idx].tolist(),
    }
    metrics_path.write_text(
        json.dumps(to_jsonable(metadata), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Resultado CNN temporal clasificacion ===")
    print(f"Input: {args.input}")
    print(f"Parcelas: {len(x)}")
    print(f"Timesteps: {x.shape[1]}")
    print(f"Features por fecha: {x.shape[2]}")
    print(f"Clases: {class_names}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Macro F1: {metrics['macro_f1']:.4f}")
    print(f"Weighted F1: {metrics['weighted_f1']:.4f}")
    print(f"Modelo: {model_path}")
    print(f"Metricas: {metrics_path}")
    return metadata


def main() -> None:
    args = parse_args()
    train(args)


if __name__ == "__main__":
    main()
