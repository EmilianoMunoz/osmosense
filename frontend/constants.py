PRIORIDAD_ORDEN = ["critica", "alta", "media", "baja"]
PRIORIDAD_LABELS = {
    "critica": "Crítica",
    "alta": "Alta",
    "media": "Media",
    "baja": "Baja",
    "sin ranking": "Sin ranking",
}
PRIORIDAD_COLOR = {
    "critica": "#d73027",
    "alta": "#fc8d59",
    "media": "#fee08b",
    "baja": "#1a9850",
    "sin ranking": "#bdbdbd",
}
PRIORIDAD_ORDEN_MAPA = PRIORIDAD_ORDEN + ["sin ranking"]
CONFIANZA_COLOR = {
    "alta": "#1a9850",
    "media": "#fee08b",
    "baja": "#d73027",
    "sin_ranking": "#bdbdbd",
}
ACCION_COLOR = {
    "bajar_confianza_no_suavizar_score": "#fdae61",
    "mantener_alerta": "#74add1",
    "revisar_visual_antes_de_suavizar": "#d73027",
    "bajar_confianza_y_revisar_geometria": "#762a83",
    "sin_accion": "#bdbdbd",
}
ACTION_LABELS = {
    "bajar_confianza_no_suavizar_score": "Bajar confianza",
    "mantener_alerta": "Mantener alerta",
    "revisar_visual_antes_de_suavizar": "Revisar visualmente",
    "bajar_confianza_y_revisar_geometria": "Revisar geometría",
    "sin_accion": "Sin alerta",
}
DIAGNOSTIC_LABELS = {
    "probable_manejo_real_o_condicion_persistente": "Condición persistente",
    "probable_ruido_o_lectura_puntual": "Lectura puntual",
    "indeterminado": "Indeterminado",
}
