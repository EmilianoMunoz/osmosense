import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import os
import numpy as np

FEATURES = ["ndvi", "ndmi", "ndwi", "msi", "savi",
            "b2", "b3", "b4", "b8", "b11",
            "mes_sin", "mes_cos"]
TARGET   = "cultivo"
RUTA_MODELO = "models/clasificador_cultivo.pkl"


def cargar_dataset(ruta: str = "data/dataset_vid_olivo.csv") -> pd.DataFrame:
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"Dataset no encontrado en {ruta}")

    df = pd.read_csv(ruta)

    # codificación circular del mes
    if "mes_sin" not in df.columns:
        df["mes_sin"] = np.sin(2 * np.pi * df["mes"] / 12)
        df["mes_cos"] = np.cos(2 * np.pi * df["mes"] / 12)

    print(f"Dataset cargado: {df.shape[0]} muestras, "
          f"{df[TARGET].value_counts().to_dict()}")
    return df

def entrenar_clasificador(df: pd.DataFrame) -> tuple:
    """Entrena un clasificador Random Forest para distinguir vid de olivo.

    Divide el dataset en entrenamiento y prueba, entrena el modelo
    y evalúa su rendimiento con métricas estándar y validación cruzada.

    Random Forest fue elegido por su robustez con datasets pequeños,
    resistencia al sobreajuste, y capacidad de medir importancia
    de features, lo cual es valioso para la interpretación en la tesis.

    Args:
        df: DataFrame con columnas de features y columna 'cultivo'.

    Returns:
        Tupla (modelo entrenado, label encoder, reporte de métricas).
    """
    X = df[FEATURES]
    y = df[TARGET]

    # codificar etiquetas (vid=1, olivo=0)
    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    # dividir en entrenamiento (80%) y prueba (20%)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_enc, test_size=0.2, random_state=42, stratify=y_enc
    )

    print(f"\nEntrenamiento: {len(X_train)} muestras")
    print(f"Prueba:        {len(X_test)} muestras")

    # entrenar modelo
    modelo = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=4,
        random_state=42,
        class_weight="balanced"
    )
    modelo.fit(X_train, y_train)

    # evaluar en conjunto de prueba
    y_pred = modelo.predict(X_test)
    reporte = classification_report(
        y_test, y_pred,
        target_names=le.classes_,
        output_dict=True
    )

    print("\nReporte de clasificación:")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    print("Matriz de confusión:")
    print(confusion_matrix(y_test, y_pred))

    # validación cruzada (5 folds)
    scores = cross_val_score(modelo, X, y_enc, cv=5, scoring="accuracy")
    print(f"\nValidación cruzada (5 folds):")
    print(f"  Accuracy por fold: {[round(s, 3) for s in scores]}")
    print(f"  Media: {scores.mean():.3f} ± {scores.std():.3f}")

    # importancia de features
    print("\nImportancia de features:")
    importancias = pd.Series(
        modelo.feature_importances_, index=FEATURES
    ).sort_values(ascending=False)
    for feature, importancia in importancias.items():
        print(f"  {feature}: {importancia:.3f}")

    return modelo, le, reporte


def guardar_modelo(modelo, le: LabelEncoder) -> None:
    """Guarda el modelo entrenado y el label encoder en disco.

    Args:
        modelo: Modelo RandomForest entrenado.
        le: LabelEncoder con las clases del target.

    Returns:
        None
    """
    os.makedirs(os.path.dirname(RUTA_MODELO), exist_ok=True)
    joblib.dump({"modelo": modelo, "label_encoder": le}, RUTA_MODELO)
    print(f"\nModelo guardado en {RUTA_MODELO}")


def predecir_cultivo(features: dict) -> str:
    """Predice el tipo de cultivo para una parcela nueva.

    Carga el modelo entrenado y predice la clase para un vector
    de features espectrales.

    Args:
        features: Diccionario con keys ndvi, ndmi, ndwi, msi, savi.

    Returns:
        String con el cultivo predicho: 'vid' u 'olivo'.

    Example:
        >>> predecir_cultivo({
        ...     "ndvi": 0.42, "ndmi": 0.18,
        ...     "ndwi": -0.21, "msi": 0.81, "savi": 0.63
        ... })
        'vid'
    """
    if not os.path.exists(RUTA_MODELO):
        raise FileNotFoundError(f"Modelo no encontrado en {RUTA_MODELO}. "
                                f"Entrenar primero.")
    data   = joblib.load(RUTA_MODELO)
    modelo = data["modelo"]
    le     = data["label_encoder"]

    X = pd.DataFrame([features])[FEATURES]
    y_pred = modelo.predict(X)
    return le.inverse_transform(y_pred)[0]

def predecir_cultivo_con_umbral(
    features: dict,
    umbral_confianza: float = 0.63
) -> dict:
    """Predice el tipo de cultivo con umbral de confianza.

    Si la probabilidad máxima de cualquier clase es menor al umbral,
    la parcela se clasifica como 'otros' en lugar de forzar una
    clasificación incorrecta.

    Args:
        features: Diccionario con keys de los features del modelo.
        umbral_confianza: Probabilidad mínima para aceptar la
            predicción. Default 0.6.

    Returns:
        Diccionario con cultivo predicho, probabilidad y confianza.

    Example:
        >>> resultado = predecir_cultivo_con_umbral({
        ...     "ndvi": 0.08, "ndmi": -0.18, ...
        ... })
        >>> print(resultado)
        {"cultivo": "vid", "probabilidad": 0.82, "confianza": "alta"}
    """
    if not os.path.exists(RUTA_MODELO):
        raise FileNotFoundError(f"Modelo no encontrado en {RUTA_MODELO}.")

    data   = joblib.load(RUTA_MODELO)
    modelo = data["modelo"]
    le     = data["label_encoder"]

    X = pd.DataFrame([features])[FEATURES]

    probabilidades = modelo.predict_proba(X)[0]
    prob_maxima    = probabilidades.max()
    clase_idx      = probabilidades.argmax()

    if prob_maxima < umbral_confianza:
        cultivo    = "otros"
        confianza  = "baja"
    elif prob_maxima < 0.75:
        cultivo    = le.inverse_transform([clase_idx])[0]
        confianza  = "media"
    else:
        cultivo    = le.inverse_transform([clase_idx])[0]
        confianza  = "alta"

    return {
        "cultivo":      cultivo,
        "probabilidad": round(float(prob_maxima), 3),
        "confianza":    confianza,
        "prob_vid":     round(float(probabilidades[list(le.classes_).index("vid")]), 3),
        "prob_olivo":   round(float(probabilidades[list(le.classes_).index("olivo")]), 3),
    }
