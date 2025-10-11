# train_mood.py
import argparse, joblib, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, f1_score, confusion_matrix

warnings.filterwarnings("ignore", category=UserWarning)

ALLOWED_MOODS = None  # e.g., set(["joy","sadness","anger","fear"]) to enforce

def load_dataset(path: str):
    # infer ; or , but prefer ; (your file)
    try:
        df = pd.read_csv(path, sep=";")
    except Exception:
        df = pd.read_csv(path)  # fallback

    if not {"label", "mood"}.issubset(df.columns):
        raise ValueError("CSV must have columns: label;mood")

    # basic cleaning
    df = df.dropna(subset=["label", "mood"]).copy()
    df["label"] = df["label"].astype(str).str.strip()
    df["mood"]  = df["mood"].astype(str).str.strip()

    # fix cases like "fear  this is my dataset small copy"
    df["mood"] = df["mood"].str.split().str[0]

    # normalize to lowercase
    df["mood"] = df["mood"].str.lower()

    # optional: enforce a whitelist of moods
    if ALLOWED_MOODS:
        df = df[df["mood"].isin(ALLOWED_MOODS)].copy()

    # drop empties after cleaning
    df = df[(df["label"] != "") & (df["mood"] != "")]
    if len(df) == 0:
        raise ValueError("No rows left after cleaning. Check your CSV.")
    return df

def main(data, out, test_size, random_state, c, max_iter):
    df = load_dataset(data)
    X, y = df["label"].values, df["mood"].values

    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state
    )

    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            min_df=1,          # small dataset → allow rare terms
            max_df=0.95,
            strip_accents="unicode"
        )),
        ("clf", LogisticRegression(
            C=c,
            max_iter=max_iter,
            class_weight="balanced",
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
            "vectorizer": "Tfidf(1-2gram, min_df=1, max_df=0.95)",
            "classifier": "LogisticRegression(class_weight=balanced)",
            "train_size": len(Xtr),
            "test_size": len(Xte),
            "random_state": random_state
        }
    }, out)
    print(f"Saved model → {out.resolve()}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="CSV with columns: label;mood (semicolon-delimited)")
    ap.add_argument("--out", default="models/mood_tfidf.joblib")
    ap.add_argument("--test_size", type=float, default=0.2)
    ap.add_argument("--random_state", type=int, default=42)
    ap.add_argument("--C", type=float, default=2.0, help="LogReg regularization strength (inverse of lambda)")
    ap.add_argument("--max_iter", type=int, default=2000)
    args = ap.parse_args()
    main(args.data, args.out, args.test_size, args.random_state, args.C, args.max_iter)    