"""
SACA - Shared train/test split

Generates the single train/test split that ALL FIVE classifier
approaches must use for training and evaluation. This is what makes
the Sprint 4 comparison table (accuracy/precision/recall across all
approaches) valid - if each person split the data differently, the
comparison would be meaningless.

Run this once, commit the two output CSVs to the repo. Everyone
building an ML approach loads FROM THESE FILES, not from
saca_dataset.csv directly.

Fixed random_state=42 makes this split reproducible - running this
script again will always produce the identical split.
"""

import pandas as pd
from sklearn.model_selection import train_test_split

INPUT_FILE = "saca_dataset.csv"
TRAIN_OUTPUT = "saca_train.csv"
TEST_OUTPUT = "saca_test.csv"
TEST_SIZE = 0.2
RANDOM_STATE = 42  # fixed seed - do not change, or the split changes for everyone

def main():
    df = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(df)} rows from {INPUT_FILE}")
    print(f"Severity distribution:\n{df['severity'].value_counts()}\n")

    # Stratify by severity so train/test have proportional representation
    # of each tier - important since CRITICAL/LOW are likely imbalanced.
    train_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=df["severity"]
    )

    train_df.to_csv(TRAIN_OUTPUT, index=False)
    test_df.to_csv(TEST_OUTPUT, index=False)

    print(f"Train set: {len(train_df)} rows -> {TRAIN_OUTPUT}")
    print(f"Train severity distribution:\n{train_df['severity'].value_counts()}\n")

    print(f"Test set: {len(test_df)} rows -> {TEST_OUTPUT}")
    print(f"Test severity distribution:\n{test_df['severity'].value_counts()}\n")

if __name__ == "__main__":
    main()