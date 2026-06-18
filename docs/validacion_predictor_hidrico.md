# Validacion del Predictor Hidrico

Reporte generado desde validacion historica contra observaciones Sentinel-2 futuras.

## Cobertura

- Fechas evaluadas: 26
- Rango: 2023-01-11 a 2026-05-06

## Resumen Global Por Cultivo Y Horizonte

| cultivo | horizon_days | fechas | n_promedio | mae | rmse | bias | spearman | top10_overlap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| global | 5 | 25 | 906.080 | 4.079 | 5.865 | -0.925 | 0.958 | 0.835 |
| global | 10 | 25 | 843.960 | 4.659 | 6.663 | -1.032 | 0.951 | 0.817 |
| olivo | 5 | 23 | 318.043 | 3.660 | 5.091 | -1.540 | 0.965 | 0.864 |
| olivo | 10 | 23 | 292.652 | 3.521 | 4.988 | -1.174 | 0.971 | 0.842 |
| vid | 5 | 25 | 613.320 | 4.277 | 6.159 | -0.634 | 0.956 | 0.835 |
| vid | 10 | 25 | 574.560 | 5.191 | 7.324 | -0.968 | 0.942 | 0.809 |

## Error Operativo

Porcentaje de predicciones dentro de 5 y 10 puntos de error absoluto.

| cultivo | horizon_days | n | pct_error_le_5 | pct_error_le_10 | direction_accuracy | obs_delta_mean | pred_delta_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| global | 5 | 22652 | 0.730 | 0.921 | 0.641 | 0.603 | -0.322 |
| global | 10 | 21099 | 0.678 | 0.889 | 0.633 | 0.811 | -0.222 |
| olivo | 5 | 7319 | 0.782 | 0.937 | 0.632 | 1.145 | -0.390 |
| olivo | 10 | 6735 | 0.776 | 0.942 | 0.638 | 1.287 | 0.116 |
| vid | 5 | 15333 | 0.705 | 0.914 | 0.645 | 0.345 | -0.289 |
| vid | 10 | 14364 | 0.631 | 0.864 | 0.630 | 0.587 | -0.380 |

## Resumen Por Estacion

| estacion | cultivo | horizon_days | fechas | mae | spearman | top10_overlap |
| --- | --- | --- | --- | --- | --- | --- |
| invierno | global | 5 | 4 | 3.722 | 0.969 | 0.819 |
| invierno | global | 10 | 4 | 4.237 | 0.955 | 0.804 |
| invierno | olivo | 5 | 4 | 3.150 | 0.975 | 0.823 |
| invierno | olivo | 10 | 4 | 3.281 | 0.969 | 0.780 |
| invierno | vid | 5 | 4 | 4.028 | 0.970 | 0.835 |
| invierno | vid | 10 | 4 | 4.773 | 0.950 | 0.809 |
| otono | global | 5 | 7 | 5.085 | 0.941 | 0.804 |
| otono | global | 10 | 7 | 5.596 | 0.944 | 0.786 |
| otono | olivo | 5 | 5 | 4.291 | 0.944 | 0.829 |
| otono | olivo | 10 | 5 | 3.224 | 0.976 | 0.841 |
| otono | vid | 5 | 7 | 5.393 | 0.940 | 0.811 |
| otono | vid | 10 | 7 | 6.476 | 0.933 | 0.782 |
| primavera | global | 5 | 7 | 3.852 | 0.957 | 0.837 |
| primavera | global | 10 | 7 | 4.459 | 0.949 | 0.815 |
| primavera | olivo | 5 | 7 | 3.889 | 0.961 | 0.861 |
| primavera | olivo | 10 | 7 | 4.025 | 0.964 | 0.840 |
| primavera | vid | 5 | 7 | 3.833 | 0.957 | 0.841 |
| primavera | vid | 10 | 7 | 4.670 | 0.942 | 0.814 |
| verano | global | 5 | 7 | 3.692 | 0.968 | 0.870 |
| verano | global | 10 | 7 | 4.405 | 0.955 | 0.852 |
| verano | olivo | 5 | 7 | 3.216 | 0.979 | 0.920 |
| verano | olivo | 10 | 7 | 3.336 | 0.978 | 0.892 |
| verano | vid | 5 | 7 | 3.925 | 0.962 | 0.852 |
| verano | vid | 10 | 7 | 4.912 | 0.945 | 0.828 |

## Fechas A Revisar

| criterio | fecha | estacion | horizon_days | n | mae | rmse | bias | spearman | top10_overlap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mayor_mae | 2026-05-06 | otono | 10 | 596 | 9.933 | 11.759 | -3.122 | 0.953 | 0.683 |
| mayor_mae | 2026-04-16 | otono | 10 | 449 | 7.640 | 10.569 | -2.898 | 0.867 | 0.533 |
| mayor_mae | 2023-01-11 | verano | 5 | 517 | 7.551 | 10.339 | -0.692 | 0.872 | 0.654 |
| mayor_mae | 2023-03-12 | otono | 5 | 794 | 7.417 | 9.801 | -1.234 | 0.878 | 0.787 |
| mayor_mae | 2024-09-17 | primavera | 5 | 1033 | 7.208 | 10.335 | 0.444 | 0.866 | 0.750 |
| mayor_mae | 2024-03-01 | otono | 5 | 890 | 6.977 | 10.199 | -5.130 | 0.907 | 0.719 |
| mayor_mae | 2024-10-07 | primavera | 10 | 805 | 6.209 | 8.992 | -2.090 | 0.905 | 0.679 |
| mayor_mae | 2023-03-12 | otono | 10 | 239 | 6.115 | 8.522 | -3.636 | 0.921 | 0.792 |
| menor_spearman | 2024-09-17 | primavera | 5 | 1033 | 7.208 | 10.335 | 0.444 | 0.866 | 0.750 |
| menor_spearman | 2026-04-16 | otono | 10 | 449 | 7.640 | 10.569 | -2.898 | 0.867 | 0.533 |
| menor_spearman | 2023-01-11 | verano | 5 | 517 | 7.551 | 10.339 | -0.692 | 0.872 | 0.654 |
| menor_spearman | 2023-03-12 | otono | 5 | 794 | 7.417 | 9.801 | -1.234 | 0.878 | 0.787 |
| menor_spearman | 2024-10-07 | primavera | 10 | 805 | 6.209 | 8.992 | -2.090 | 0.905 | 0.679 |
| menor_spearman | 2024-03-01 | otono | 5 | 890 | 6.977 | 10.199 | -5.130 | 0.907 | 0.719 |
| menor_spearman | 2024-09-17 | primavera | 10 | 596 | 5.822 | 8.656 | 0.749 | 0.908 | 0.683 |
| menor_spearman | 2023-03-12 | otono | 10 | 239 | 6.115 | 8.522 | -3.636 | 0.921 | 0.792 |

## Lectura

- `MAE` indica error promedio en puntos de score hidrico sobre escala 0-100.
- `Spearman` mide si el modelo mantiene bien el orden relativo de parcelas.
- `top10_overlap` mide coincidencia entre el 10% de parcelas mas criticas predichas y observadas.
- `direction_accuracy` mide si el modelo acierta el signo de la evolucion respecto del riesgo actual.
