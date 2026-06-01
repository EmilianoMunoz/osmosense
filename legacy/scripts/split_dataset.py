import pandas as pd
import argparse
from sklearn.model_selection import train_test_split


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera split train/validation/test.")
    parser.add_argument("--input", default="data/dataset_fenologico_recalculado.csv")
    parser.add_argument("--train-output", default="data/train.csv")
    parser.add_argument("--validation-output", default="data/validation.csv")
    parser.add_argument("--test-output", default="data/test_final.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = pd.read_csv(args.input)

    train_val, test = train_test_split(
        df,
        test_size=0.2,
        stratify=df["cultivo"],
        random_state=42
    )

    train, validation = train_test_split(
        train_val,
        test_size=0.25,
        stratify=train_val["cultivo"],
        random_state=42
    )

    train.to_csv(args.train_output, index=False)
    validation.to_csv(args.validation_output, index=False)
    test.to_csv(args.test_output, index=False)

    print("Input:", args.input, df.shape)
    print("Train:", train.shape)
    print("Validation:", validation.shape)
    print("Test:", test.shape)


if __name__ == "__main__":
    main()
