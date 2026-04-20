import pandas as pd
from typing import Literal

NivelEstres = Literal["sin_estres", "bajo", "medio", "alto"]


def clasificar_estres_ndmi(ndmi: float) -> NivelEstres:
    """Clasifica el nivel de estrés hídrico según el índice NDMI.

    El NDMI (Normalized Difference Moisture Index) es el indicador
    principal de estrés hídrico. Mide el contenido de agua foliar
    directamente, detectando déficit hídrico antes de que aparezcan
    síntomas visibles.

    Umbrales basados en literatura de teledetección agrícola para
    zonas áridas y semiáridas (Gao, 1996; Jackson et al., 2004):
        - sin_estres : NDMI > 0.2
        - bajo       : 0.0 <= NDMI <= 0.2
        - medio      : -0.2 <= NDMI < 0.0
        - alto       : NDMI < -0.2

    Args:
        ndmi: Valor del índice NDMI entre -1 y 1.

    Returns:
        Nivel de estrés como string: 'sin_estres', 'bajo',
        'medio' o 'alto'.

    Example:
        >>> clasificar_estres_ndmi(0.05)
        'bajo'
        >>> clasificar_estres_ndmi(-0.25)
        'alto'
    """
    if ndmi > 0.2:
        return "sin_estres"
    elif ndmi >= 0.0:
        return "bajo"
    elif ndmi >= -0.2:
        return "medio"
    else:
        return "alto"


def clasificar_estres_msi(msi: float) -> NivelEstres:
    """Clasifica el nivel de estrés hídrico según el índice MSI.

    El MSI (Moisture Stress Index) tiene interpretación inversa
    al NDMI: valores más altos indican mayor estrés hídrico.

    Umbrales:
        - sin_estres : MSI < 0.6
        - bajo       : 0.6 <= MSI < 1.0
        - medio      : 1.0 <= MSI < 1.5
        - alto       : MSI >= 1.5

    Args:
        msi: Valor del índice MSI, rango común 0.2 a 3.0.

    Returns:
        Nivel de estrés como string: 'sin_estres', 'bajo',
        'medio' o 'alto'.

    Example:
        >>> clasificar_estres_msi(1.1)
        'medio'
    """
    if msi < 0.6:
        return "sin_estres"
    elif msi < 1.0:
        return "bajo"
    elif msi < 1.5:
        return "medio"
    else:
        return "alto"


def clasificar_estres_ndvi(ndvi: float) -> NivelEstres:
    """Clasifica el nivel de estrés hídrico según el índice NDVI.

    El NDVI es un indicador indirecto de estrés hídrico. Valores
    bajos indican reducción del vigor vegetativo, que puede ser
    consecuencia de déficit hídrico sostenido.

    Umbrales:
        - sin_estres : NDVI > 0.5
        - bajo       : 0.3 <= NDVI <= 0.5
        - medio      : 0.1 <= NDVI < 0.3
        - alto       : NDVI < 0.1

    Args:
        ndvi: Valor del índice NDVI entre -1 y 1.

    Returns:
        Nivel de estrés como string: 'sin_estres', 'bajo',
        'medio' o 'alto'.

    Example:
        >>> clasificar_estres_ndvi(0.35)
        'bajo'
    """
    if ndvi > 0.5:
        return "sin_estres"
    elif ndvi >= 0.3:
        return "bajo"
    elif ndvi >= 0.1:
        return "medio"
    else:
        return "alto"


def _nivel_a_numero(nivel: NivelEstres) -> int:
    """Convierte un nivel de estrés a valor numérico para promediarlo.

    Args:
        nivel: Nivel de estrés como string.

    Returns:
        Valor entero: sin_estres=0, bajo=1, medio=2, alto=3.
    """
    return {"sin_estres": 0, "bajo": 1, "medio": 2, "alto": 3}[nivel]


def _numero_a_nivel(numero: float) -> NivelEstres:
    """Convierte un valor numérico promedio a nivel de estrés.

    Args:
        numero: Valor numérico promedio entre 0 y 3.

    Returns:
        Nivel de estrés como string.
    """
    if numero < 0.5:
        return "sin_estres"
    elif numero < 1.5:
        return "bajo"
    elif numero < 2.5:
        return "medio"
    else:
        return "alto"


def clasificar_estres_combinado(
    ndmi: float,
    msi: float,
    ndvi: float
) -> NivelEstres:
    """Clasifica el nivel de estrés hídrico combinando tres índices.

    Combina las clasificaciones individuales de NDMI, MSI y NDVI
    usando un promedio ponderado donde NDMI tiene el doble de peso
    por ser el índice más específico para estrés hídrico foliar.

    Pesos:
        - NDMI: 50%
        - MSI:  30%
        - NDVI: 20%

    Args:
        ndmi: Valor del índice NDMI entre -1 y 1.
        msi: Valor del índice MSI, rango común 0.2 a 3.0.
        ndvi: Valor del índice NDVI entre -1 y 1.

    Returns:
        Nivel de estrés combinado: 'sin_estres', 'bajo',
        'medio' o 'alto'.

    Example:
        >>> clasificar_estres_combinado(0.05, 0.94, 0.47)
        'bajo'
    """
    nivel_ndmi = _nivel_a_numero(clasificar_estres_ndmi(ndmi))
    nivel_msi  = _nivel_a_numero(clasificar_estres_msi(msi))
    nivel_ndvi = _nivel_a_numero(clasificar_estres_ndvi(ndvi))

    promedio_ponderado = (nivel_ndmi * 0.5) + (nivel_msi * 0.3) + (nivel_ndvi * 0.2)

    return _numero_a_nivel(promedio_ponderado)


def aplicar_clasificacion(
    resultados: list,
    ruta_salida: str = "data/resultados_estres.csv"
) -> pd.DataFrame:
    """Aplica la clasificación de estrés hídrico a una lista de resultados.

    Toma los resultados de índices espectrales por parcela y agrega
    la clasificación individual por cada índice y la clasificación
    combinada final.

    Args:
        resultados: Lista de diccionarios con ndvi, ndmi, msi
            y metadatos de parcela.
        ruta_salida: Ruta del CSV de salida con clasificaciones.
            Default 'data/resultados_estres.csv'.

    Returns:
        DataFrame con columnas originales más estres_ndmi,
        estres_msi, estres_ndvi y estres_combinado.

    Example:
        >>> df = aplicar_clasificacion(resultados)
        >>> print(df[["parcela_id", "estres_combinado"]])
    """
    df = pd.DataFrame(resultados)

    df["estres_ndmi"]     = df["ndmi"].apply(clasificar_estres_ndmi)
    df["estres_msi"]      = df["msi"].apply(clasificar_estres_msi)
    df["estres_ndvi"]     = df["ndvi"].apply(clasificar_estres_ndvi)
    df["estres_combinado"] = df.apply(
        lambda row: clasificar_estres_combinado(
            row["ndmi"], row["msi"], row["ndvi"]
        ),
        axis=1
    )

    df.to_csv(ruta_salida, index=False)
    print(f"\nClasificación guardada en {ruta_salida}")
    return df