from app.services.clasificador import predecir_cultivo_con_umbral

if __name__ == "__main__":

    # caso 1 — valores reales de vid en julio 2024
    vid_julio = {
        "ndvi": 0.5964, "ndmi": 0.1689, "ndwi": -0.6219,
        "msi": 0.7242, "savi": 0.8945,
        "b2": 408.0749, "b3": 701.0233, "b4": 756.7599,
        "b8": 3131.0186, "b11": 2179.0658,
        "mes_sin": -0.5, "mes_cos": -0.866
    }

    # caso 2 — valores reales de olivo en julio 2024
    olivo_julio = {
        "ndvi": 0.4424, "ndmi": -0.1014, "ndwi": -0.5885,
        "msi": 1.231, "savi": 0.6635,
        "b2": 254.0076, "b3": 418.5164, "b4": 623.9478,
        "b8": 1594.4314, "b11": 1947.8554,
        "mes_sin": -0.5, "mes_cos": -0.866
    }

    # caso 3 — valores sintéticos de suelo desnudo
    # reflectancias altas en visible, NDVI muy bajo
    suelo_desnudo = {
        "ndvi": 0.03, "ndmi": -0.35, "ndwi": -0.52,
        "msi": 2.10, "savi": 0.04,
        "b2": 1200.0, "b3": 1350.0, "b4": 1480.0,
        "b8": 1580.0, "b11": 3120.0,
        "mes_sin": -0.5, "mes_cos": -0.866
    }

    print("=== Test clasificador con umbral de confianza ===\n")

    for nombre, features in [
        ("Vid en julio (real)",   vid_julio),
        ("Olivo en julio (real)", olivo_julio),
        ("Suelo desnudo (sint.)", suelo_desnudo),
    ]:
        resultado = predecir_cultivo_con_umbral(features, umbral_confianza=0.63)
        print(f"{nombre}:")
        print(f"  Predicción: {resultado['cultivo']}")
        print(f"  Confianza:  {resultado['confianza']} ({resultado['probabilidad']})")
        print(f"  Prob vid:   {resultado['prob_vid']}")
        print(f"  Prob olivo: {resultado['prob_olivo']}")
        print()