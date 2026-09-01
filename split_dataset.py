"""
SACA - Shared train/test split

Generates the single train/test split that ALL FIVE classifier
approaches must use for training and evaluation. This is what makes
the Sprint 4/5 comparison table (accuracy/precision/recall across all
approaches) valid - if each person split the data differently, the
comparison would be meaningless.

Run this once, commit the two output CSVs to the repo. Everyone
building an ML approach loads FROM THESE FILES, not from
saca_dataset.csv directly.

Fixed random_state=42 makes this split reproducible - running this
script again will always produce the identical split.

--- FIX (Sprint 5) ---
The original version of this script called train_test_split() on the
raw rows directly. saca_dataset.csv has heavy duplication - the same
symptom_text combination repeats many times (304 unique combos across
3936+984 rows) - so a row-level split scattered copies of the same
exact example into both train and test. Every single test row's exact
symptom_text turned out to also appear in train (984/984), which is
why every classifier trained on the old split scored unrealistically
high (SVM hit 99.9%) - it was memorizing, not generalizing.

This version splits at the UNIQUE symptom_text level first, then
assigns every row (including duplicates) to whichever side its
symptom_text landed on. No symptom_text value can appear in both
train and test. A hard assertion checks this before writing the files
- if it ever fails, nothing gets written, so a silently-broken split
can't happen again.
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

    n_unique = df["symptom_text"].nunique()
    print(f"Unique symptom_text combinations: {n_unique} (out of {len(df)} rows - "
          f"{len(df) - n_unique} duplicate rows)\n")

    # Split at the level of UNIQUE symptom_text values, not raw rows, so that
    # duplicate rows of the same combination can't end up on both sides.
    # One representative row per unique symptom_text carries the stratification label.
    unique_df = df.drop_duplicates(subset="symptom_text")

    train_keys, test_keys = train_test_split(
        unique_df,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=unique_df["severity"],
    )

    train_symptom_texts = set(train_keys["symptom_text"])
    test_symptom_texts = set(test_keys["symptom_text"])

    # Every row (including duplicates) goes to whichever side its
    # symptom_text was assigned to above.
    train_df = df[df["symptom_text"].isin(train_symptom_texts)]
    test_df = df[df["symptom_text"].isin(test_symptom_texts)]

    # Hard guardrail: this is the exact bug we're fixing, so verify it's
    # actually gone before writing anything out.
    overlap = train_symptom_texts & test_symptom_texts
    assert len(overlap) == 0, (
        f"LEAKAGE: {len(overlap)} symptom_text values appear in both train "
        f"and test - refusing to write output files."
    )
    assert len(train_df) + len(test_df) == len(df), (
        "Row count mismatch after split - some rows were dropped or duplicated."
    )

    train_df.to_csv(TRAIN_OUTPUT, index=False)
    test_df.to_csv(TEST_OUTPUT, index=False)

    print("No symptom_text overlap between train and test - verified.\n")

    print(f"Train set: {len(train_df)} rows ({len(train_symptom_texts)} unique) -> {TRAIN_OUTPUT}")
    print(f"Train severity distribution:\n{train_df['severity'].value_counts()}\n")

    print(f"Test set: {len(test_df)} rows ({len(test_symptom_texts)} unique) -> {TEST_OUTPUT}")
    print(f"Test severity distribution:\n{test_df['severity'].value_counts()}\n")

if __name__ == "__main__":
    main()