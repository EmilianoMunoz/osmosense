import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier


TRAIN_PATH = "data/train.csv"
VALIDATION_PATH = "data/validation.csv"
TEST_PATH = "data/test_final.csv"
MODEL_PATH = "models/clasificador_multiclass.pkl"
FEATURE_IMPORTANCE_PATH = "data/feature_importance_multiclass.csv"

RANDOM_STATE = 42


def mapear_clase(clase: str) -> str:
    if clase in ["vid", "frutales", "olivo"]:
        return clase
    return "no_cultivo"


def cargar_split(path: str) -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(path)
    y = df["cultivo"].map(mapear_clase)
    return df, y


def columnas_numericas(df: pd.DataFrame) -> list[str]:
    return [
        col
        for col in df.select_dtypes(include=[np.number]).columns
        if col != "parcela_id"
    ]


def columnas_por_prefijo(df: pd.DataFrame, prefijos: tuple[str, ...]) -> list[str]:
    return [col for col in columnas_numericas(df) if col.startswith(prefijos)]


def columnas_mensuales_mean(df: pd.DataFrame, prefijos: tuple[str, ...]) -> list[str]:
    return [
        col
        for col in columnas_por_prefijo(df, prefijos)
        if "_mean_" in col
    ]


def columnas_agregadas(df: pd.DataFrame, prefijos: tuple[str, ...]) -> list[str]:
    columnas = []

    for col in columnas_numericas(df):
        if "_2023_" in col or "_2024_" in col:
            continue
        if not col.startswith(prefijos):
            continue
        columnas.append(col)

    return columnas


def features_ganadoras(df: pd.DataFrame) -> list[str]:
    indices = (
        "ndvi_", "ndmi_", "ndwi_", "msi_", "savi_", "ndre_",
        "gndvi_", "evi_", "bsi_", "nbr_", "mtci_", "ireci_",
    )
    bandas = ("b2_", "b3_", "b4_", "b5_", "b6_", "b7_", "b8_", "b11_", "b12_")
    prefijos = indices + bandas

    return sorted(
        set(columnas_mensuales_mean(df, prefijos))
        | set(columnas_agregadas(df, prefijos))
    )


def crear_modelo(num_classes: int) -> XGBClassifier:
    return XGBClassifier(
        objective="multi:softprob",
        num_class=num_classes,
        n_estimators=350,
        max_depth=5,
        learning_rate=0.04,
        subsample=0.9,
        colsample_bytree=0.85,
        gamma=0.2,
        min_child_weight=2,
        reg_lambda=1.5,
        reg_alpha=0.0,
        eval_metric="mlogloss",
        tree_method="hist",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )


def evaluar(model, features, df, y_true, encoder: LabelEncoder) -> dict:
    pred_encoded = model.predict(df[features]).astype(int)
    pred = encoder.inverse_transform(pred_encoded)

    return {
        "accuracy": accuracy_score(y_true, pred),
        "macro_f1": f1_score(y_true, pred, average="macro"),
        "pred": pred,
    }


def entrenar_y_evaluar(
    features: list[str],
    train_df: pd.DataFrame,
    y_train_encoded: np.ndarray,
    sample_weight: np.ndarray,
    validation_df: pd.DataFrame,
    y_validation: pd.Series,
    test_df: pd.DataFrame,
    y_test: pd.Series,
    encoder: LabelEncoder,
) -> dict:
    model = crear_modelo(len(encoder.classes_))
    model.fit(train_df[features], y_train_encoded, sample_weight=sample_weight)

    validation_score = evaluar(model, features, validation_df, y_validation, encoder)
    test_score = evaluar(model, features, test_df, y_test, encoder)

    return {
        "features": features,
        "model": model,
        "validation_accuracy": validation_score["accuracy"],
        "validation_macro_f1": validation_score["macro_f1"],
        "test_accuracy": test_score["accuracy"],
        "test_macro_f1": test_score["macro_f1"],
        "test_pred": test_score["pred"],
    }


def main() -> None:
    train_df, y_train = cargar_split(TRAIN_PATH)
    validation_df, y_validation = cargar_split(VALIDATION_PATH)
    test_df, y_test = cargar_split(TEST_PATH)

    encoder = LabelEncoder()
    y_train_encoded = encoder.fit_transform(y_train)
    sample_weight = compute_sample_weight("balanced", y_train_encoded)

    base_features = features_ganadoras(train_df)

    print("=== Seleccion de features multiclass ===\n", flush=True)
    print(f"Base features: {len(base_features)}", flush=True)

    print("Entrenando modelo base para importancias...", flush=True)
    base_model = crear_modelo(len(encoder.classes_))
    base_model.fit(train_df[base_features], y_train_encoded, sample_weight=sample_weight)

    importancias = (
        pd.Series(base_model.feature_importances_, index=base_features)
        .sort_values(ascending=False)
        .reset_index()
    )
    importancias.columns = ["feature", "importance"]
    importancias.to_csv(FEATURE_IMPORTANCE_PATH, index=False)
    print(f"Importancias guardadas en {FEATURE_IMPORTANCE_PATH}", flush=True)

    ordered_features = importancias["feature"].tolist()
    top_k_values = [100, 150, 200, 250, 300, 400, 500, 660]
    resultados = []

    for top_k in top_k_values:
        features = ordered_features[:top_k]
        print(f"Entrenando top_{top_k}...", flush=True)
        resultado = entrenar_y_evaluar(
            features,
            train_df,
            y_train_encoded,
            sample_weight,
            validation_df,
            y_validation,
            test_df,
            y_test,
            encoder,
        )
        resultado["top_k"] = top_k
        resultados.append(resultado)

        print(
            f"top_{top_k:<3d} "
            f"val_acc={resultado['validation_accuracy']:.3f} "
            f"val_f1={resultado['validation_macro_f1']:.3f} "
            f"test_acc={resultado['test_accuracy']:.3f} "
            f"test_f1={resultado['test_macro_f1']:.3f}",
            flush=True,
        )

    best = max(resultados, key=lambda item: item["validation_macro_f1"])

    print("\n=== Mejor por validation macro-F1 ===")
    print(f"Top K: {best['top_k']}")
    print(f"Validation accuracy: {best['validation_accuracy']:.4f}")
    print(f"Validation macro-F1: {best['validation_macro_f1']:.4f}")
    print(f"Test accuracy: {best['test_accuracy']:.4f}")
    print(f"Test macro-F1: {best['test_macro_f1']:.4f}")

    print("\nReporte test:")
    print(classification_report(y_test, best["test_pred"]))
    print("Matriz de confusion test:")
    print(confusion_matrix(y_test, best["test_pred"], labels=encoder.classes_))
    print(f"Labels matriz: {list(encoder.classes_)}")

    joblib.dump(
        {
            "model": best["model"],
            "features": best["features"],
            "label_encoder": encoder,
            "classes": list(encoder.classes_),
            "source_dataset": "data/dataset_fenologico_recalculado.csv",
            "variant": f"top_{best['top_k']}_indices_bandas_mean_mas_agregadas",
            "selection_metric": "validation_macro_f1",
        },
        MODEL_PATH,
    )

    print(f"\nModelo multiclass actualizado en {MODEL_PATH}")


if __name__ == "__main__":
    main()
