import argparse
import joblib
import os
import sys
import json
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, f1_score, confusion_matrix

warnings.filterwarnings("ignore", category=UserWarning)

# Modified load_dataset to accept label_col
def load_dataset(path: str, label_col: str):
    df = pd.read_csv(path)
    
    if label_col not in df.columns:
        raise ValueError(f"Dataset must contain a '{label_col}' column.")
    if "text" not in df.columns:
        raise ValueError("Dataset must contain a 'text' column.")
        
    df = df.dropna(subset=["text", label_col]).copy()
    df["text"] = df["text"].astype(str).str.strip()
    df[label_col] = df[label_col].astype(str).str.strip()
    
    # Rename the specified label column to 'label' for consistency with the pipeline
    df["label"] = df[label_col]
    
    return df

def main(data, out, test_size, random_state, c, max_iter, label_col):
    df = load_dataset(data, label_col)
    X, y = df["text"].values, df["label"].values

    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state
    )

    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.9,
            strip_accents="unicode"
        )),
        ("clf", LogisticRegression(
            C=c,
            max_iter=max_iter,
            class_weight="balanced",  # still safe even if your dataset is perfectly balanced
            n_jobs=None
        ))
    ])

    pipe.fit(Xtr, ytr)

    yhat = pipe.predict(Xte)
    print(classification_report(yte, yhat, digits=3))
    print("Macro-F1:", round(f1_score(yte, yhat, average="macro"), 4))
    print(f"Labels for '{label_col}':", sorted(np.unique(y)))
    print("Confusion matrix (rows=true, cols=pred):")
    print(confusion_matrix(yte, yhat, labels=sorted(np.unique(y))))

    # Determine output path and metadata based on label_col
    if label_col == "genre":
        # Use a specific output path for genre models if not overridden
        output_model_path = out if out != "models/mood_tfidf.joblib" else "models/genre_classifier.joblib"
    else: # Default to mood or other label columns
        output_model_path = out

    out_path = Path(output_model_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    model_metadata = {
        "vectorizer": "Tfidf(1-2gram, min_df=2, max_df=0.9)",
        "classifier": "LogisticRegression(class_weight=balanced)",
        "train_size": len(Xtr),
        "test_size": len(Xte),
        "random_state": random_state,
        "label_column": label_col # Store which column was used for training
    }

    joblib.dump({
        "pipeline": pipe,
        "labels": sorted(np.unique(y)),
        "metadata": model_metadata
    }, out_path)
    print(f"Saved model → {out_path.resolve()}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="CSV with columns: text + label_col")
    ap.add_argument("--out", default="models/mood_tfidf.joblib", help="Output path for the trained model.")
    ap.add_argument("--test_size", type=float, default=0.2, help="Proportion of the dataset to include in the test split.")
    ap.add_argument("--random_state", type=int, default=42, help="Controls the shuffling applied to the data before applying the split.")
    ap.add_argument("--C", type=float, default=2.0, help="LogReg regularization strength (inverse of lambda).")
    ap.add_argument("--max_iter", type=int, default=2000, help="Maximum number of iterations for the solver.")
    # Added argument for label column
    ap.add_argument("--label_col", default="mood", help="Name of the label column in the dataset (e.g., 'mood', 'genre'). Defaults to 'mood'.")
    
    args = ap.parse_args()
    
    # Call main with the new label_col argument
    main(args.data, args.out, args.test_size, args.random_state, args.C, args.max_iter, args.label_col)
