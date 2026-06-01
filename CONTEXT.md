CONTEXT.md
PROJECT NAME

Satellite Crop Classification + Hydric Stress Forecasting

PROJECT GOAL

Build a production-ready Machine Learning pipeline capable of:

Classifying agricultural parcels using Sentinel-derived spectral features
Predicting hydric stress 7 days ahead for:
grapevine (vid)
olive groves (olivo)

The project is focused on agricultural remote sensing and temporal modeling.

CURRENT STATUS

The classification pipeline is already implemented and functional.

Current stages:

cultivo vs no_cultivo
olivo vs resto
vid vs frutales

The pipeline uses hierarchical classification.

CURRENT PIPELINE ARCHITECTURE
INPUT FEATURES
      ↓
[ Modelo 1 ]
cultivo vs no_cultivo
      ↓
if cultivo:
      ↓
[ Modelo 2 ]
olivo vs resto
      ↓
if not olivo:
      ↓
[ Modelo 3 ]
vid vs frutales
      ↓
FINAL CLASS

Final classes:

vid
frutales
olivo
no_cultivo
TECH STACK
Python 3.12
Pandas
NumPy
Scikit-learn
XGBoost
Joblib

Environment:

Ubuntu Linux
venv virtual environment
REPOSITORY STRUCTURE
project_root/
│
├── data/
│   ├── train.csv
│   ├── test_final.csv
│
├── models/
│   ├── clasificador_cultivo.pkl
│   ├── clasificador_olivo.pkl
│   ├── clasificador_vid_frutales.pkl
│
├── scripts/
│   ├── clasificador_cultivo.py
│   ├── clasificador_olivo.py
│   ├── clasificador_vid_frutales.py
│   ├── pipeline_inferencia.py
│
└── CONTEXT.md
DATASET DESCRIPTION

Main dataset:

CSV format
Each row represents one parcel/sample
Numerical satellite-derived features
One target column:
cultivo

Possible cultivo values:

vid
frutales
olivo
descarte

Internally:

descarte → mapped to no_cultivo
FEATURE TYPES

The dataset contains:

1. Monthly spectral features

Examples:

ndvi_mean_2023_01
ndvi_std_2023_01
ndwi_mean_2023_01
ndmi_mean_2023_01
msi_mean_2023_01
savi_mean_2023_01

Also includes:

min
max
std
spectral bands

Across multiple months and years.

2. Aggregated phenological features

These are extremely important.

Examples:

ndvi_max_year
ndvi_min_year
ndvi_amp_year
ndvi_mean_year
ndvi_std_year
ndvi_slope
ndvi_coeff_var
ndvi_diff_mean
ndvi_growth_total
ndvi_decline_total
ndvi_peak_month
ndvi_diff_verano_invierno

These features currently produce much better results than raw monthly features.

IMPORTANT IMPLEMENTATION DETAIL

The project previously suffered from:

ValueError: feature_names mismatch

Cause:
Models were trained using reduced feature sets,
but inference used the full dataset columns.

This was fixed by saving features together with the model.

Correct structure:

joblib.dump(
    {
        "model": model,
        "threshold": best_threshold,
        "features": list(X.columns)
    },
    path
)

During inference:

x = x.reindex(columns=FEATURES, fill_value=0)

This pattern MUST be preserved.

CURRENT MODEL DETAILS
MODEL 1 — cultivo vs no_cultivo

Goal:
Detect agricultural parcels.

Output:

1 → cultivo
0 → no_cultivo

Current notes:

good recall
slightly aggressive toward no_cultivo
MODEL 2 — olivo vs resto

Goal:
Detect olive groves.

Output:

1 → olivo
0 → other crops

Uses:

XGBoost
threshold calibration
MODEL 3 — vid vs frutales

This is currently the strongest model.

Important:
Uses ONLY aggregated phenological features.

Key features:

features_clave = [
    "ndvi_max_year",
    "ndvi_min_year",
    "ndvi_amp_year",
    "ndvi_mean_year",
    "ndvi_std_year",
    "ndvi_slope",
    "ndvi_coeff_var",
    "ndvi_diff_mean",
    "ndvi_diff_std",
    "ndvi_diff_max",
    "ndvi_diff_min",
    "ndvi_growth_total",
    "ndvi_decline_total",
    "ndvi_diff_verano_invierno",
    "ndvi_peak_month",
]

Current performance:

~0.69 accuracy inside vid vs frutales task
CURRENT GLOBAL PERFORMANCE

Pipeline accuracy:
~0.61

Main problems:

vid/frutales confusion
cascading errors from hierarchical pipeline
excessive no_cultivo predictions

Important insight:
Phenological engineered features perform MUCH better than raw monthly data.

CURRENT INFERENCE LOGIC

Current order:

1. cultivo vs no_cultivo
2. olivo vs resto
3. vid vs frutales

Potential future improvement:
probabilistic ensemble instead of rigid cascade.

COMMANDS
Train models
python scripts/clasificador_cultivo.py
python scripts/clasificador_olivo.py
python scripts/clasificador_vid_frutales.py
Run inference
python scripts/pipeline_inferencia.py
CODING RULES

IMPORTANT:

Do NOT invent feature names
Do NOT change column naming conventions
Always preserve model feature compatibility
Always save thresholds with models
Always save feature lists with models
Avoid adding unnecessary dependencies
Prefer Pandas + NumPy + sklearn + XGBoost
Preserve current repository structure
NEXT MAJOR GOAL

Hydric stress prediction at +7 days.

HYDRIC STRESS FORECASTING OBJECTIVE

Move from:

static classification

to:

temporal forecasting

for:

vid
olivo
FUTURE PIPELINE
Satellite Time Series
        ↓
Crop Classification
        ↓
Filter:
vid + olivo
        ↓
Temporal Dataset Builder
        ↓
Hydric Stress Forecast Model
        ↓
Stress prediction at t+7
FUTURE INPUTS

Potential time-series variables:

NDVI
NDWI
NDMI
MSI
SAVI

Potential future climate variables:

temperature
precipitation
evapotranspiration
FUTURE TARGET

Hydric stress at +7 days.

Possible implementations:

Option 1 — Binary classification
stress = 1 if ndwi < threshold else 0

Recommended initial approach.

Option 2 — Continuous regression

Predict continuous stress index.

TEMPORAL DATASET IDEA

For each parcel:

t-30 ... t → input features
t+7 → target

Example:

NDVI_t-7
NDVI_t-6
NDVI_t-5
...
NDWI_t
→
stress_t+7
FUTURE FEATURE ENGINEERING

Important future features:

rolling_mean
rolling_std
slope
recent_drop
temporal_variability
seasonality

Examples:

ndvi_slope_7d
ndwi_drop
ndmi_trend
FUTURE MODELS
Baseline
XGBoost
Better
LightGBM
Advanced
LSTM
GRU
Temporal Transformers
IMPORTANT DOMAIN INSIGHT

The major improvement will NOT come from:

endlessly tuning XGBoost

The major improvement WILL come from:

proper temporal modeling
better phenological representation
climate integration
CURRENT DEVELOPMENT PRIORITIES
SHORT TERM
Improve classification accuracy
Unify phenological features across all models
Reduce cascading errors
Improve vid/frutales separation
MEDIUM TERM
Build temporal dataset generator
Define hydric stress labels
Train baseline forecasting model
LONG TERM
Climate integration
Sequence models (LSTM/GRU)
Multi-step forecasting
Production deployment
IMPORTANT CONSTRAINTS
Keep solutions simple first
Avoid premature complexity
Prefer interpretable features initially
Preserve reproducibility
Avoid breaking feature compatibility
Do not refactor repository structure unnecessarily
EXPECTED ASSISTANT BEHAVIOR

When modifying code:

preserve existing architecture
preserve feature compatibility
avoid hallucinated columns
use real repository paths
prefer incremental improvements
explain WHY changes are made
avoid rewriting unrelated files
END OF CONTEXT