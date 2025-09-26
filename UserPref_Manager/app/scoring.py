# app/scoring.py
import numpy as np

def z(x: np.ndarray) -> np.ndarray:
    return (x - x.mean()) / (x.std() + 1e-8)

def score(user_vec: np.ndarray, session_vec: np.ndarray, cand_vecs: np.ndarray,
          genre_boost: np.ndarray = None, skip_penalty: np.ndarray = None) -> np.ndarray:
    sim_long = cand_vecs @ user_vec
    sim_sess = cand_vecs @ session_vec if session_vec is not None else np.zeros_like(sim_long)
    g = genre_boost if genre_boost is not None else np.zeros_like(sim_long)
    p = skip_penalty if skip_penalty is not None else np.zeros_like(sim_long)
    base = 0.55*z(sim_long) + 0.25*z(sim_sess) + 0.10*z(g) - 0.05*p
    return base
