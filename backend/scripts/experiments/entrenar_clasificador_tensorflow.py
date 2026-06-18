from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_class_weight


INPUT_PATH = "backend/data/dataset_temporal_hidrico.csv"
OUTPUT_DIR = Path("backend/models/clasificador_tensorflow")
DEFAULT_CLASSES = ["vid", "olivo"]
RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Entrena una red neuronal TensorFlow/Keras para clasificacion de cultivo. "
            "Es un experimento aislado: no reemplaza el clasificador operativo."
        )
    )
    parser.add_argument("--input", default=INPUT_PATH)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--target", default="cultivo")
    parser.add_argument("--classes", nargs="+", default=DEFAULT_CLASSES)
    parser.add_argument("--group-col", default="parcela_id")
    parser.add_argument(
        "--feature-set",
        choices=["mean", "mean-std", "wide-spectral", "all"],
        default="mean-std",
        help="Conjunto de features numericas a usar.",
    )
    parser.add_argument(
        "--features",
        default=None,
        help="Lista explicita separada por coma. Si se informa, ignora --feature-set.",
    )
    parser.add_argument("--include-area", action="store_true")
    parser.add_argument("--test-size", type=float, default=0.20)
    parser.add_argument("--validation-size", type=float, default=0.15)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.25)
    parser.add_argument("--hidden-units", nargs="+", type=int, default=[128, 64])
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Limita filas para una corrida rapida, seleccionando grupos completos.",
    )
    parser.add_argument("--random-state", type=int, default=RANDOM_STATE)
    return parser.parse_args()


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
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


def parse_feature_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def classification_feature_columns(
    df: pd.DataFrame,
    target: str,
    feature_set: str,
    explicit_features: list[str] | None = None,
    include_area: bool = False,
) -> list[str]:
    if explicit_features is not None:
        missing = [col for col in explicit_features if col not in df.columns]
        if missing:
            raise ValueError(f"Features inexistentes: {missing}")
        return explicit_features

    excluded = {
        target,
        "parcela_id",
        "fid",
        "id",
        "fecha",
        "fecha_fin",
        "year",
        "month",
        "day_of_year",
        "window_days",
    }
    excluded_prefixes = ("scl_",)
    temporal = {"month_sin", "month_cos", "doy_sin", "doy_cos"}
    spectral_wide_tokens = (
        "_mean_",
        "_stddev_",
        "_min_",
        "_max_",
        "_max_year",
        "_min_year",
        "_amp_year",
        "_mean_year",
        "_std_year",
        "_coeff_var",
        "_slope",
        "_diff_mean",
        "_diff_std",
        "_growth_total",
        "_decline_total",
        "_peak_month",
        "_diff_verano_invierno",
    )
    numeric_cols = list(df.select_dtypes(include=[np.number]).columns)

    features: list[str] = []
    for col in numeric_cols:
        if col in excluded or col.startswith(excluded_prefixes):
            continue
        if col == "area_m2" and not include_area:
            continue
        if col in temporal:
            features.append(col)
            continue
        if feature_set == "mean" and col.endswith("_mean"):
            features.append(col)
        elif feature_set == "mean-std" and col.endswith(("_mean", "_stddev")):
            features.append(col)
        elif feature_set == "wide-spectral" and any(token in col for token in spectral_wide_tokens):
            if "_count_" not in col:
                features.append(col)
        elif feature_set == "all":
            features.append(col)

    return features


def limit_rows_by_groups(
    df: pd.DataFrame,
    group_col: str,
    max_rows: int | None,
    random_state: int,
) -> pd.DataFrame:
    if max_rows is None or len(df) <= max_rows or group_col not in df.columns:
        return df

    group_sizes = df.groupby(group_col).size().sample(frac=1, random_state=random_state)
    selected_groups = []
    total = 0
    for group_id, size in group_sizes.items():
        selected_groups.append(group_id)
        total += int(size)
        if total >= max_rows:
            break
    return df[df[group_col].isin(selected_groups)].copy()


def _has_all_classes(part: pd.DataFrame, target: str, classes: set[str]) -> bool:
    return set(part[target].dropna().astype(str).unique()) == classes


def split_train_validation_test(
    df: pd.DataFrame,
    target: str,
    group_col: str,
    test_size: float,
    validation_size: float,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    classes = set(df[target].dropna().astype(str).unique())

    if group_col in df.columns and df[group_col].nunique() >= 10:
        for seed_offset in range(30):
            seed = random_state + seed_offset
            test_splitter = GroupShuffleSplit(
                n_splits=1,
                test_size=test_size,
                random_state=seed,
            )
            train_val_pos, test_pos = next(
                test_splitter.split(df, groups=df[group_col].astype(str))
            )
            train_val = df.iloc[train_val_pos]
            test = df.iloc[test_pos]
            relative_val_size = validation_size / max(1e-9, 1 - test_size)
            val_splitter = GroupShuffleSplit(
                n_splits=1,
                test_size=relative_val_size,
                random_state=seed,
            )
            train_rel_pos, val_rel_pos = next(
                val_splitter.split(train_val, groups=train_val[group_col].astype(str))
            )
            train_pos = train_val_pos[train_rel_pos]
            val_pos = train_val_pos[val_rel_pos]
            train = df.iloc[train_pos]
            val = df.iloc[val_pos]

            if all(_has_all_classes(part, target, classes) for part in [train, val, test]):
                return train_pos, val_pos, test_pos, "group"

        raise RuntimeError("No se pudo generar split por parcela con todas las clases.")

    train_val_idx, test_idx = train_test_split(
        np.arange(len(df)),
        test_size=test_size,
        stratify=df[target],
        random_state=random_state,
    )
    relative_val_size = validation_size / max(1e-9, 1 - test_size)
    train_idx, val_idx = train_test_split(
        train_val_idx,
        test_size=relative_val_size,
        stratify=df.iloc[train_val_idx][target],
        random_state=random_state,
    )
    return train_idx, val_idx, test_idx, "stratified_rows"


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


def build_model(
    tf: Any,
    input_dim: int,
    n_classes: int,
    hidden_units: list[int],
    dropout: float,
    learning_rate: float,
    l2_value: float,
):
    inputs = tf.keras.Input(shape=(input_dim,), name="features")
    x = inputs
    for units in hidden_units:
        x = tf.keras.layers.Dense(
            units,
            activation="relu",
            kernel_regularizer=tf.keras.regularizers.l2(l2_value),
        )(x)
        x = tf.keras.layers.BatchNormalization()(x)
        x = tf.keras.layers.Dropout(dropout)(x)
    outputs = tf.keras.layers.Dense(n_classes, activation="softmax", name="cultivo")(x)
    model = tf.keras.Model(inputs=inputs, outputs=outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def prepare_dataset(args: argparse.Namespace) -> tuple[pd.DataFrame, list[str], LabelEncoder]:
    df = pd.read_csv(args.input)
    df = add_temporal_features(df)
    df = df[df[args.target].notna()].copy()
    df[args.target] = df[args.target].astype(str).str.strip().str.lower()
    if args.classes:
        valid_classes = {item.lower() for item in args.classes}
        df = df[df[args.target].isin(valid_classes)].copy()

    df = limit_rows_by_groups(df, args.group_col, args.max_rows, args.random_state)
    if df.empty:
        raise RuntimeError("Dataset vacio despues de filtrar clases/filas.")

    features = classification_feature_columns(
        df,
        args.target,
        args.feature_set,
        parse_feature_list(args.features),
        include_area=args.include_area,
    )
    if not features:
        raise RuntimeError("No se detectaron features numericas para entrenar.")

    label_encoder = LabelEncoder()
    df["_target_encoded"] = label_encoder.fit_transform(df[args.target])
    return df, features, label_encoder


def distribution(df: pd.DataFrame, target: str) -> dict[str, int]:
    return {str(key): int(value) for key, value in df[target].value_counts().items()}


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def binary_threshold_metrics(
    y_val: np.ndarray,
    val_probabilities: np.ndarray,
    y_test: np.ndarray,
    test_probabilities: np.ndarray,
    class_names: list[str],
) -> dict[str, Any] | None:
    if len(class_names) != 2:
        return None

    thresholds = np.linspace(0.05, 0.95, 91)
    best = {"threshold": 0.5, "validation_macro_f1": -1.0}
    for threshold in thresholds:
        val_pred = (val_probabilities[:, 1] >= threshold).astype(int)
        score = f1_score(y_val, val_pred, average="macro")
        if score > best["validation_macro_f1"]:
            best = {
                "threshold": float(threshold),
                "validation_macro_f1": float(score),
            }

    threshold = float(best["threshold"])
    test_pred = (test_probabilities[:, 1] >= threshold).astype(int)
    report = classification_report(
        y_test,
        test_pred,
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )
    return {
        **best,
        "accuracy": float(accuracy_score(y_test, test_pred)),
        "macro_f1": float(f1_score(y_test, test_pred, average="macro")),
        "weighted_f1": float(f1_score(y_test, test_pred, average="weighted")),
        "predictions": test_pred,
        "report": report,
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    tf = import_tensorflow()
    tf.keras.utils.set_random_seed(args.random_state)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df, features, label_encoder = prepare_dataset(args)
    train_idx, val_idx, test_idx, split_mode = split_train_validation_test(
        df,
        args.target,
        args.group_col,
        args.test_size,
        args.validation_size,
        args.random_state,
    )

    train_df = df.iloc[train_idx].copy()
    val_df = df.iloc[val_idx].copy()
    test_df = df.iloc[test_idx].copy()

    x_train_raw = train_df[features].replace([np.inf, -np.inf], np.nan)
    x_val_raw = val_df[features].replace([np.inf, -np.inf], np.nan)
    x_test_raw = test_df[features].replace([np.inf, -np.inf], np.nan)

    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    x_train = scaler.fit_transform(imputer.fit_transform(x_train_raw))
    x_val = scaler.transform(imputer.transform(x_val_raw))
    x_test = scaler.transform(imputer.transform(x_test_raw))

    y_train = train_df["_target_encoded"].to_numpy()
    y_val = val_df["_target_encoded"].to_numpy()
    y_test = test_df["_target_encoded"].to_numpy()

    class_weights_raw = compute_class_weight(
        class_weight="balanced",
        classes=np.unique(y_train),
        y=y_train,
    )
    class_weight = {
        int(label): float(weight)
        for label, weight in zip(np.unique(y_train), class_weights_raw)
    }

    model = build_model(
        tf=tf,
        input_dim=x_train.shape[1],
        n_classes=len(label_encoder.classes_),
        hidden_units=args.hidden_units,
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
            patience=max(3, args.patience // 2),
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

    val_probabilities = model.predict(x_val, batch_size=args.batch_size, verbose=0)
    probabilities = model.predict(x_test, batch_size=args.batch_size, verbose=0)
    y_pred = probabilities.argmax(axis=1)
    class_names = label_encoder.classes_.tolist()

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
        "split_mode": split_mode,
    }

    model_path = output_dir / "clasificador_tensorflow.keras"
    preprocess_path = output_dir / "preprocesamiento.joblib"
    metrics_path = output_dir / "metricas_clasificador_tensorflow.json"
    report_path = output_dir / "classification_report.csv"
    confusion_path = output_dir / "confusion_matrix.csv"
    threshold_report_path = output_dir / "classification_report_threshold.csv"
    threshold_confusion_path = output_dir / "confusion_matrix_threshold.csv"
    history_path = output_dir / "history.csv"

    model.save(model_path)
    joblib.dump(
        {
            "imputer": imputer,
            "scaler": scaler,
            "label_encoder": label_encoder,
            "features": features,
            "target": args.target,
            "classes": class_names,
        },
        preprocess_path,
    )
    pd.DataFrame(report).T.to_csv(report_path)
    pd.DataFrame(
        confusion_matrix(y_test, y_pred),
        index=class_names,
        columns=class_names,
    ).to_csv(confusion_path)
    threshold_result = binary_threshold_metrics(
        y_val,
        val_probabilities,
        y_test,
        probabilities,
        class_names,
    )
    threshold_metrics = None
    if threshold_result is not None:
        threshold_metrics = {
            key: value
            for key, value in threshold_result.items()
            if key not in {"predictions", "report"}
        }
        pd.DataFrame(threshold_result["report"]).T.to_csv(threshold_report_path)
        pd.DataFrame(
            confusion_matrix(y_test, threshold_result["predictions"]),
            index=class_names,
            columns=class_names,
        ).to_csv(threshold_confusion_path)
    pd.DataFrame(history.history).to_csv(history_path, index=False)

    metadata = {
        "input": args.input,
        "target": args.target,
        "classes": class_names,
        "features": features,
        "feature_set": args.feature_set,
        "include_area": bool(args.include_area),
        "split_mode": split_mode,
        "group_col": args.group_col,
        "n_rows": int(len(df)),
        "n_features": int(len(features)),
        "n_train": int(len(train_df)),
        "n_validation": int(len(val_df)),
        "n_test": int(len(test_df)),
        "distribution_total": distribution(df, args.target),
        "distribution_train": distribution(train_df, args.target),
        "distribution_validation": distribution(val_df, args.target),
        "distribution_test": distribution(test_df, args.target),
        "class_weight": class_weight,
        "hidden_units": args.hidden_units,
        "dropout": args.dropout,
        "learning_rate": args.learning_rate,
        "l2": args.l2,
        "model_path": str(model_path),
        "preprocess_path": str(preprocess_path),
        "metrics": metrics,
        "threshold_metrics": threshold_metrics,
    }
    metrics_path.write_text(
        json.dumps(to_jsonable(metadata), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Resultado TensorFlow clasificacion ===")
    print(f"Input: {args.input}")
    print(f"Split: {split_mode}")
    print(f"Filas: train={len(train_df)} val={len(val_df)} test={len(test_df)}")
    print(f"Features: {len(features)}")
    print(f"Clases: {class_names}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Macro F1: {metrics['macro_f1']:.4f}")
    print(f"Weighted F1: {metrics['weighted_f1']:.4f}")
    if threshold_metrics is not None:
        print(
            "Threshold optimizado: "
            f"{threshold_metrics['threshold']:.2f} "
            f"macro_f1={threshold_metrics['macro_f1']:.4f} "
            f"accuracy={threshold_metrics['accuracy']:.4f}"
        )
    print(f"Modelo: {model_path}")
    print(f"Metricas: {metrics_path}")

    return metadata


def main() -> None:
    args = parse_args()
    train(args)


if __name__ == "__main__":
    main()
