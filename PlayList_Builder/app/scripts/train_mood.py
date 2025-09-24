import argparse, joblib, os, sys, json, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, f1_score, confusion_matrix

warnings.filterwarnings("ignore", category=UserWarning)

def load_dataset(path: str):
    df = pd.read_csv(path)
    # Normalize expected columns: we accept label/mood/mood_id
    if "label" not in df.columns:
        if "mood" in df.columns:
            df["label"] = df["mood"]
        elif "mood_id" in df.columns:
            df["label"] = df["mood_id"].astype(str)  # stringify if numeric
        else:
            raise ValueError("Dataset must contain one of: 'label', 'mood', or 'mood_id'.")
    if "text" not in df.columns:
        raise ValueError("Dataset must contain a 'text' column.")
    df = df.dropna(subset=["text", "label"]).copy()
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()
    return df

def main(data, out, test_size, random_state, c, max_iter):
    df = load_dataset(data)
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
    print("Labels:", sorted(np.unique(y)))
    print("Confusion matrix (rows=true, cols=pred):")
    print(confusion_matrix(yte, yhat, labels=sorted(np.unique(y))))

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "pipeline": pipe,
        "labels": sorted(np.unique(y)),
        "metadata": {
            "vectorizer": "Tfidf(1-2gram, min_df=2, max_df=0.9)",
            "classifier": "LogisticRegression(class_weight=balanced)",
            "train_size": len(Xtr),
            "test_size": len(Xte),
            "random_state": random_state
        }
    }, out)
    print(f"Saved model → {out.resolve()}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="CSV with columns: text + (label|mood|mood_id)")
    ap.add_argument("--out", default="models/mood_tfidf.joblib")
    ap.add_argument("--test_size", type=float, default=0.2)
    ap.add_argument("--random_state", type=int, default=42)
    ap.add_argument("--C", type=float, default=2.0, help="LogReg regularization strength (inverse of lambda)")
    ap.add_argument("--max_iter", type=int, default=2000)
    args = ap.parse_args()
    main(args.data, args.out, args.test_size, args.random_state, args.C, args.max_iter)
