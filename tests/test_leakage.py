"""Leakage and validation-integrity checks for the earnings models (run on the fixture warehouse)."""

import os
import subprocess
import sys

import duckdb
import numpy as np
import pytest
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline

from campuspulse import config as C
from campuspulse import load, model


@pytest.fixture(scope="module")
def df():
    os.environ["CP_ROW_FLOOR"] = "250"
    load.run(fixture=True)
    subprocess.run(
        [sys.executable, "-m", "dbt.cli.main", "build", "--profiles-dir", ".", "-q"], cwd=C.ROOT / "dbt", check=True, env=os.environ
    )
    return model.load_data(True)


def test_no_earnings_derived_field_is_a_feature(df):
    assert not set(model.FEATURES) & set(model.EXCLUDED)
    assert not [f for f in model.FEATURES if "earn" in f]
    assert set(model.FEATURES) <= set(df.columns)


def test_mart_model_input_exposes_no_earnings_derived_columns_besides_target(df):
    cols = set(duckdb.connect(str(load.db_path(True)), read_only=True).sql("select * from marts.mart_model_input limit 0").df().columns)
    leaked = {c for c in cols if ("earn" in c and c not in ("median_earnings_p10", "log_median_earnings_p10")) or c == "debt_to_earnings"}
    assert not leaked, leaked


def test_every_excluded_field_has_a_written_reason():
    assert all(len(v) > 10 for v in model.EXCLUDED.values())


def test_folds_never_split_an_institution(df):
    folds = model.fold_ids(df.unitid)
    per_inst = df.assign(f=folds).groupby("unitid").f.nunique()
    assert (per_inst == 1).all()
    assert set(np.unique(folds)) == set(range(model.N_FOLDS))


def test_shuffled_target_scores_near_zero_out_of_fold(df):
    """If features secretly contained the target, a permuted target would still be predictable. It must not be."""
    rng = np.random.default_rng(0)
    d = df.assign(**{model.TARGET: rng.permutation(df[model.TARGET].to_numpy())})
    folds = model.fold_ids(d.unitid)
    pred = np.empty(len(d))
    for k in range(model.N_FOLDS):
        m = Pipeline([("pre", model.linear_pre()), ("m", LinearRegression())]).fit(
            d.loc[folds != k, model.FEATURES], d.loc[folds != k, model.TARGET]
        )
        pred[folds == k] = m.predict(d.loc[folds == k, model.FEATURES])
    y = d[model.TARGET].to_numpy()
    assert 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2) < 0.03


def test_baseline_falls_back_when_cell_unseen(df):
    b = model.Baseline(True).fit(df[df.state != "FL"])
    p = b.predict(df[df.state == "FL"].head(5))
    assert np.isfinite(p).all()


def test_shap_is_additive_for_the_scored_model(df):
    import shap

    m = model.hgb().fit(df[model.FEATURES], df[model.TARGET])
    pre, est = m.named_steps["pre"], m.named_steps["m"]
    X = pre.transform(df[model.FEATURES])[:300]
    expl = shap.TreeExplainer(est)
    err = np.abs(expl.shap_values(X).sum(axis=1) + expl.expected_value - est.predict(X)).max()
    assert err < 1e-6
