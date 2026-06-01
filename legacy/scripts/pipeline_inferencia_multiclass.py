import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix


DATA_PATH = "data/test_final.csv"
MODEL_PATH = "models/clasificador_multiclass.pkl"


def mapear_clase(clase: str) -> str:
    if clase in ["vid", "frutales", "olivo"]:
        return clase
    return "no_cultivo"


print("Cargando modelo multiclass...")
data = joblib.load(MODEL_PATH)
model = data["model"]
features = data["features"]
label_encoder = data["label_encoder"]

print("Modelo cargado correctamente\n")

df = pd.read_csv(DATA_PATH)

print(f"Dataset: {len(df)} muestras")
print("Distribución real:", df["cultivo"].value_counts().to_dict())

X = df.drop(columns=["cultivo"], errors="ignore")
X = X.select_dtypes(include=[np.number])
X = X.reindex(columns=features, fill_value=0)

y_true = np.array([mapear_clase(c) for c in df["cultivo"].values])
y_pred_encoded = model.predict(X).astype(int)
y_pred = label_encoder.inverse_transform(y_pred_encoded)

print("\n=== RESULTADOS MULTICLASS ===\n")
print(classification_report(y_true, y_pred))

print("Matriz de confusión:")
print(confusion_matrix(y_true, y_pred, labels=label_encoder.classes_))
print("Labels matriz:", list(label_encoder.classes_))

accuracy = np.mean(y_pred == y_true)
print(f"\nAccuracy multiclass: {accuracy:.4f}")

df_resultados = df.copy()
df_resultados["real"] = y_true
df_resultados["pred"] = y_pred

errores = df_resultados[df_resultados["real"] != df_resultados["pred"]]

print(f"\nTotal errores: {len(errores)}")

print("\nErrores por clase real:")
print(errores["real"].value_counts())

print("\nErrores por predicción:")
print(errores["pred"].value_counts())
