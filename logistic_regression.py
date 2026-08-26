"""
Logistic Regression Classifier for SACA.
"""

import os
import sys
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.pipeline import Pipeline
import joblib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classifier.base import BaseClassifier


class LogisticRegressionClassifier(BaseClassifier):
    
    name = "logistic_regression"
    
    def __init__(self, model_path=None):
        super().__init__()
        self.model_path = model_path
        self.pipeline = None
        self.label_encoder = None
        self.is_trained = False
        
    def _load_data(self, filepath):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Data file not found: {filepath}")
        
        df = pd.read_csv(filepath)
        df = df.dropna(subset=['symptom_text', 'severity'])
        df['symptom_text'] = df['symptom_text'].astype(str).str.lower().str.strip()
        df['severity'] = df['severity'].astype(str).str.upper().str.strip()
        return df
    
    def train(self, train_path="saca_train.csv"):
        print(f"[LogisticRegression] Loading training data from {train_path}...")
        df = self._load_data(train_path)
        
        X = df['symptom_text'].values
        y = df['severity'].values
        
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y)
        
        self.pipeline = Pipeline([
            ('vectorizer', CountVectorizer(
                lowercase=True,
                strip_accents='unicode',
                stop_words='english',
                max_features=500,
                min_df=2,
                max_df=0.8
            )),
            ('classifier', LogisticRegression(
                C=1.0,
                max_iter=1000,
                class_weight='balanced',
                solver='lbfgs',
                random_state=42
            ))
        ])
        
        print(f"[LogisticRegression] Training on {len(X)} samples...")
        self.pipeline.fit(X, y_encoded)
        self.is_trained = True
        
        unique, counts = np.unique(y, return_counts=True)
        print("[LogisticRegression] Training class distribution:")
        for label, count in zip(unique, counts):
            print(f"  - {label}: {count} samples")
        
        print("[LogisticRegression] Training complete.")
        
    def classify(self, symptom_text: str) -> dict:
        if not self.is_trained:
            self.train()
        
        cleaned_text = symptom_text.lower().strip()
        X = [cleaned_text]
        pred_encoded = self.pipeline.predict(X)[0]
        proba = self.pipeline.predict_proba(X)[0]
        
        severity = self.label_encoder.inverse_transform([pred_encoded])[0]
        confidence = np.max(proba) * 100
        reason = f"Model predicted {severity} with {confidence:.1f}% confidence"
        
        allowed = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        if severity not in allowed:
            severity = "LOW"
        
        return self.build_result(
            severity=severity,
            symptoms=symptom_text,
            reason=reason
        )


if __name__ == "__main__":
    print("=" * 60)
    print("SACA Logistic Regression Classifier")
    print("=" * 60)
    
    clf = LogisticRegressionClassifier()
    clf.train("saca_train.csv")
    
    test_cases = [
        "itching skin rash fever",
        "shortness of breath chest pain cough",
        "headache fatigue nausea"
    ]
    
    for symptoms in test_cases:
        result = clf.classify(symptoms)
        print(f"\nInput: '{symptoms}'")
        print(f"Severity: {result['severity']}")
        print(f"Reason: {result['reason']}")