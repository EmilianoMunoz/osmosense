import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import os

from app.services.clasificador import cargar_dataset, entrenar_clasificador, guardar_modelo

FEATURES = ["ndvi", "ndmi", "ndwi", "msi", "savi",
            "b2", "b3", "b4", "b8", "b11",
            "mes_sin", "mes_cos"]
TARGET = "cultivo"

if __name__ == "__main__":

    print("=== Entrenamiento del clasificador de cultivos ===\n")

    # cargar dataset
    df = cargar_dataset("data/dataset_vid_olivo.csv")

    # entrenar
    modelo, le, reporte = entrenar_clasificador(df)

    # guardar
    guardar_modelo(modelo, le)

    # evaluación con umbral de confianza
    from sklearn.model_selection import train_test_split

    X = df[FEATURES]
    y = df[TARGET]
    le_eval = LabelEncoder()
    y_enc = le_eval.fit_transform(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_enc, test_size=0.2, random_state=42, stratify=y_enc
    )

    print("\nEvaluación con umbral de confianza (0.63):")
    probabilidades   = modelo.predict_proba(X_test)
    prob_maxima      = probabilidades.max(axis=1)

    mascara_confianza = prob_maxima >= 0.63
    X_test_conf       = X_test[mascara_confianza]
    y_test_conf       = y_test[mascara_confianza]
    y_pred_conf       = modelo.predict(X_test_conf)

    total         = len(X_test)
    con_confianza = mascara_confianza.sum()
    descartados   = total - con_confianza

    print(f"  Total muestras prueba:     {total}")
    print(f"  Con confianza >= 0.63:     {con_confianza} ({con_confianza/total*100:.1f}%)")
    print(f"  Descartadas como 'otros':  {descartados} ({descartados/total*100:.1f}%)")

    if con_confianza > 0:
        accuracy_conf = (y_pred_conf == y_test_conf).mean()
        print(f"  Accuracy sobre confiables: {accuracy_conf:.3f}")
        print("\n  Reporte sobre muestras confiables:")
        print(classification_report(y_test_conf, y_pred_conf,
                                    target_names=le_eval.classes_))

    print("\n=== Entrenamiento completado ===")