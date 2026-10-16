"""Run the seven risk-indicator tests over the cleaned spend.

Reads: outputs/analytics-full/spend_clean.csv, clean_summary.json,
       contract_suppliers.csv, contracts_summary.json, outputs/rules.json,
       data/contracts.csv (sha256 only).
Writes: outputs/analytics.json and outputs/analytics-full/<test>.csv
        (plus off_contract_candidates.csv and duplicates_clusters.csv).
All outputs describe risk indicators to investigate, not findings.
"""
import csv
import difflib
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd  # noqa: E402

from common import (ANALYTICS_JSON, CONTRACTS_CSV, CONTRACTS_FINDER_EXPORT_ROW_CAP, FULL, LANGUAGE,  # noqa: E402
                    METHOD_PARAMETERS, RULES_JSON, TAGS, enters_tier, just_under,
                    load_rules, load_tiers, sha256, testing_thresholds, trading_parts,
                    write_json)

SIMILARITY_RATIO = 0.85      # method constant (agent definition), not money
CONTAINMENT_MIN_CHARS = 6    # method constant (agent definition)
KEY_TAGS = ["care_or_education_placement", "general_procurement"]
PLACEMENT_CAVEAT = ("Placements and individual care packages are often arranged under "
                    "App C exclusions (CPR-56, CPR-61) or frameworks and may have no "
                    "notice of their own.")


def r2(x):
    return None if x is None else round(float(x), 2)


def full_path(name):
    return f"outputs/analytics-full/{name}.csv"


def entry(status="ran", reason=None, description="", rule_ids=None, parameters=None,
          name=""):
    return {"status": status, "reason": reason, "description": description,
            "rule_ids": rule_ids or [], "parameters": parameters or {}, "counts": {},
            "totals_gbp": {}, "by_tag": {}, "top_20": [], "top_5_by_tag": {},
            "full_list": full_path(name), "caveats": []}


def by_tag(df, amount_col="amount", tag_col="tag"):
    out = {}
    for t in TAGS:
        sub = df[df[tag_col] == t] if len(df) else df
        out[t] = {"count": int(len(sub)), "total_gbp": r2(sub[amount_col].sum() if len(sub) else 0)}
    return out


def tops(df, amount_col, tie_col, fields, tag_col="tag"):
    if not len(df):
        return [], {t: [] for t in TAGS}
    d = df.sort_values([amount_col, tie_col], ascending=[False, True])

    def rec(x):
        o = {}
        for f in fields:
            v = x[f]
            if isinstance(v, float):
                v = r2(v)
            elif hasattr(v, "item"):
                v = v.item()
            o[f] = v
        return o
    top20 = [rec(x) for _, x in d.head(20).iterrows()]
    t5 = {t: [rec(x) for _, x in d[d[tag_col] == t].head(5).iterrows()] for t in TAGS}
    return top20, t5


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def load_spend():
    df = pd.read_csv(os.path.join(FULL, "spend_clean.csv"), dtype=str, keep_default_na=False)
    df["amount"] = df["amount"].astype(float)
    df["timestamp"] = [datetime.fromisoformat(v) for v in df["timestamp"]]
    df["date"] = [date.fromisoformat(v) for v in df["date"]]
    return df


def supplier_table(df, factor):
    rows = []
    for sn, g in df.groupby("supplier_norm", sort=True):
        mix = g.groupby("tag")["amount"].sum()
        mix = mix.sort_index()
        main = sorted(mix.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        total = g["amount"].sum()
        rows.append({"supplier_norm": sn, "window_total": total,
                     "annualised_estimate": total * factor, "main_tag": main,
                     "tag_mix": ";".join(f"{k}:{v:.2f}" for k, v in mix.items()),
                     "raw_spellings": " | ".join(sorted(g["supplier"].unique())),
                     "n_payments": len(g),
                     "services": " | ".join(sorted(g["service"].unique())),
                     "row_ids": ";".join(sorted(g["row_id"]))})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ tests
def threshold_clustering(df, Ts, floor):
    p = METHOD_PARAMETERS
    rids = sorted({r for t in Ts for r in t["rule_ids"]} | {"CPR-07"})
    e = entry(description="Payments in the band just under each testing threshold, a "
              "risk indicator to investigate for threshold-hugging.", rule_ids=rids,
              parameters={"clustering_band_low_factor": p["clustering_band_low_factor"],
                          "comparison_band_low_factor": p["comparison_band_low_factor"],
                          "testing_thresholds": [t["T"] for t in Ts],
                          "data_floor_gbp": r2(floor)}, name="threshold_clustering")
    flagged, per_T = [], {}
    for t in Ts:
        T, inc = t["T"], t["lower_edge_inclusive"]
        lo, clo = p["clustering_band_low_factor"] * T, p["comparison_band_low_factor"] * T
        key = str(T)
        # band [0.9T, T) or [0.9T, T] lies wholly below the floor exactly when
        # the smallest kept amount already enters the tier
        if enters_tier(floor, T, inc):
            per_T[key] = {"status": "not computed", "roles": t["roles"],
                          "reason": "band lies wholly below the smallest kept amount "
                                    "(dataset publishes payments over a floor)"}
            continue
        band = df[(df["amount"] >= lo) & df["amount"].map(lambda a: just_under(a, T, inc))].copy()
        comp = df[(df["amount"] >= clo) & (df["amount"] < lo)]
        band["T"], band["roles"] = T, ",".join(t["roles"])
        band["rule_ids_T"] = ",".join(t["rule_ids"])
        band["band"] = f"[{lo:g}, {T}{']' if not inc else ')'}"
        flagged.append(band)
        tagc = {}
        for tg in TAGS:
            b, c = band[band.tag == tg], comp[comp.tag == tg]
            tagc[tg] = {"band_count": int(len(b)), "band_gbp": r2(b.amount.sum()),
                        "comparison_count": int(len(c)), "comparison_gbp": r2(c.amount.sum()),
                        "ratio_band_to_comparison": r2(len(b) / len(c)) if len(c) else None}
        per_T[key] = {"status": "ran", "roles": t["roles"], "rule_ids": t["rule_ids"],
                      "lower_edge_inclusive": inc, "band": band["band"].iloc[0] if len(band) else
                      f"[{lo:g}, {T}{']' if not inc else ')'}",
                      "comparison_band": f"[{clo:g}, {lo:g})",
                      "band_count": int(len(band)), "band_gbp": r2(band.amount.sum()),
                      "comparison_count": int(len(comp)), "comparison_gbp": r2(comp.amount.sum()),
                      "ratio_band_to_comparison": r2(len(band) / len(comp)) if len(comp) else None,
                      "by_tag": tagc}
    fl = pd.concat(flagged) if flagged else df.iloc[0:0]
    cols = ["row_id", "T", "roles", "rule_ids_T", "band", "amount", "date", "supplier",
            "supplier_norm", "tag", "service", "narrative"]
    fl[cols].sort_values(["T", "amount", "row_id"], ascending=[True, False, True]).to_csv(
        os.path.join(FULL, "threshold_clustering.csv"), index=False)
    e["counts"] = {"flagged_payments": int(len(fl)), "per_threshold": per_T}
    e["totals_gbp"] = {"flagged": r2(fl.amount.sum() if len(fl) else 0)}
    e["by_tag"] = by_tag(fl)
    e["top_20"], e["top_5_by_tag"] = tops(fl, "amount", "row_id",
                                          ["row_id", "amount", "T", "roles", "band", "date",
                                           "supplier_norm", "tag"])
    for x in e["top_20"] + [y for v in e["top_5_by_tag"].values() for y in v]:
        x["date"] = str(x["date"])
    e["caveats"] = ["A payment near a threshold is a risk indicator to investigate; the "
                    "comparison band gives context for whether the band is unusually full."]
    return e


def split_purchases(df, Ts):
    win = METHOD_PARAMETERS["split_window_days"]
    rids = sorted({"CPR-07"} | {r for t in Ts for r in t["rule_ids"]})
    e = entry(description="Groups of two or more payments to one supplier within a "
              f"{win}-day window, each under a threshold but together entering it; a "
              "risk indicator to investigate for split purchases.", rule_ids=rids,
              parameters={"split_window_days": win, "window_rule": f"[anchor date, anchor date + {win - 1} days]",
                          "testing_thresholds": [t["T"] for t in Ts]}, name="split_purchases")
    groups = []
    for t in Ts:
        T, inc = t["T"], t["lower_edge_inclusive"]
        sub = df[df["amount"].map(lambda a: just_under(a, T, inc))]
        for sn, g in sub.groupby("supplier_norm", sort=True):
            if len(g) < 2:
                continue
            g = g.sort_values(["timestamp", "row_id"]).reset_index(drop=True)
            uf, flagged_any = UF(), set()
            dates = list(g["date"])
            for i in range(len(g)):
                end = dates[i] + timedelta(days=win - 1)
                idx = [j for j in range(len(g)) if dates[i] <= dates[j] <= end]
                if len(idx) >= 2 and enters_tier(g.loc[idx, "amount"].sum(), T, inc):
                    for j in idx:
                        uf.union(idx[0], j)
                        flagged_any.add(j)
            comps = defaultdict(list)
            for j in flagged_any:
                comps[uf.find(j)].append(j)
            for members in comps.values():
                gg = g.loc[sorted(members)]
                mix = gg.groupby("tag")["amount"].sum().sort_index()
                main = sorted(mix.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                groups.append({"supplier_norm": sn, "T": T, "roles": ",".join(t["roles"]),
                               "n_payments": len(gg), "group_total": gg["amount"].sum(),
                               "first_date": str(min(gg["date"])), "last_date": str(max(gg["date"])),
                               "span_days": (max(gg["date"]) - min(gg["date"])).days,
                               "main_tag": main,
                               "tag_mix": ";".join(f"{k}:{v:.2f}" for k, v in mix.items()),
                               "row_ids": ";".join(gg["row_id"])})
    gdf = pd.DataFrame(groups, columns=["supplier_norm", "T", "roles", "n_payments", "group_total",
                                        "first_date", "last_date", "span_days", "main_tag",
                                        "tag_mix", "row_ids"])
    gdf.sort_values(["group_total", "supplier_norm", "T"], ascending=[False, True, True]).to_csv(
        os.path.join(FULL, "split_purchases.csv"), index=False)
    fields = ["supplier_norm", "T", "n_payments", "group_total", "first_date", "last_date",
              "span_days", "main_tag", "tag_mix"]  # row_ids live in the full CSV
    gp = gdf[gdf.main_tag == "general_procurement"]
    gp_top, _ = tops(gp, "group_total", "supplier_norm", fields, tag_col="main_tag")
    e["general_procurement"] = {
        "groups": int(len(gp)), "payments": int(gp.n_payments.sum()) if len(gp) else 0,
        "total_gbp": r2(gp.group_total.sum() if len(gp) else 0),
        "per_threshold": {str(T): {"groups": int((gp["T"] == T).sum()),
                                   "total_gbp": r2(gp.loc[gp["T"] == T, "group_total"].sum())}
                          for T in [t["T"] for t in Ts]},
        "top_20": gp_top}
    e["counts"] = {"groups": int(len(gdf)),
                   "payments_in_groups": int(gdf.n_payments.sum()) if len(gdf) else 0,
                   "groups_spanning_more_than_one_window": int((gdf.span_days > win - 1).sum()),
                   "per_threshold": {str(T): int((gdf["T"] == T).sum()) for T in [t["T"] for t in Ts]}}
    e["totals_gbp"] = {"groups_total": r2(gdf.group_total.sum() if len(gdf) else 0),
                       "per_threshold": {str(T): r2(gdf.loc[gdf["T"] == T, "group_total"].sum())
                                         for T in [t["T"] for t in Ts]}}
    e["by_tag"] = by_tag(gdf, "group_total", "main_tag")
    e["top_20"], e["top_5_by_tag"] = tops(gdf, "group_total", "supplier_norm", fields, "main_tag")
    e["caveats"] = ["Recurring care placements produce many groups; general_procurement is "
                    "reported separately. Overlapping windows are merged, so a group can span "
                    f"more than {win} days; each constituent window spans at most {win - 1} days.",
                    "Groups are indicators to investigate whether payments relate to one "
                    "requirement, not findings."]
    return e


def match_suppliers(sup, cs):
    """Return dict supplier_norm -> (status, candidate rows)."""
    notice_norms = set(cs["supplier_norm"])
    notice_parts = {}
    for n in notice_norms:
        notice_parts[n] = set(trading_parts(n))
    out = {}
    for sn in sup:
        if sn in notice_norms:
            out[sn] = ("exact_match", [])
            continue
        sp = set(trading_parts(sn))
        cands = []
        for n in sorted(notice_norms):
            if (sp & ({n} | notice_parts[n])) or (notice_parts[n] & ({sn} | sp)):
                cands.append(("candidate_trading_name", n, None))
        if cands:
            out[sn] = ("candidate_trading_name", cands)
            continue
        for n in sorted(notice_norms):
            ratio = difflib.SequenceMatcher(None, sn, n).ratio()
            short, long_ = sorted([sn, n], key=len)
            if ratio >= SIMILARITY_RATIO or (len(short) >= CONTAINMENT_MIN_CHARS and short in long_):
                cands.append(("candidate_similar_name", n, round(ratio, 3)))
        out[sn] = ("candidate_similar_name", cands) if cands else ("no_notice_found", [])
    return out


def off_contract(sup, cs, tiers, factor, cont, matches):
    t = next(x for x in tiers if x["tier"] == "notice_publication")
    T, inc = t["value"], t["lower_edge_inclusive"]
    rids = t["rule_ids"] + ["CPR-05"]
    e = entry(description="Suppliers whose annualised_estimate enters the notice-publication "
              "tier with no exact-match published notice found; a risk indicator to "
              "investigate, not evidence that no contract exists.", rule_ids=rids,
              parameters={"T": T, "lower_edge_inclusive": inc, "annualisation_factor": factor,
                          "similarity_ratio": SIMILARITY_RATIO,
                          "containment_min_chars": CONTAINMENT_MIN_CHARS,
                          "matched_means": "exact_match on normalised name only"},
              name="off_contract")
    pop = sup[sup.annualised_estimate.map(lambda a: enters_tier(a, T, inc))].copy()
    live_norms = set(cs.loc[cs.live_in_window.astype(str) == "True", "supplier_norm"])
    pop["match_status"] = pop.supplier_norm.map(lambda s: matches[s][0])
    pop["exact_live"] = pop.supplier_norm.map(lambda s: matches[s][0] == "exact_match" and s in live_norms)
    pop["notice_ids"] = pop.supplier_norm.map(
        lambda s: ";".join(sorted(set(cs.loc[cs.supplier_norm == s, "notice_id"]))))
    cols = ["supplier_norm", "raw_spellings", "main_tag", "tag_mix", "window_total",
            "annualised_estimate", "match_status", "exact_live", "notice_ids", "n_payments", "row_ids"]
    pop.sort_values(["annualised_estimate", "supplier_norm"], ascending=[False, True])[cols].to_csv(
        os.path.join(FULL, "off_contract.csv"), index=False)
    # candidates file
    title = dict(zip(cs.supplier_norm + "|" + cs.notice_id, cs.title))
    with open(os.path.join(FULL, "off_contract_candidates.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["supplier_norm", "match_status", "annualised_estimate", "notice_supplier_norm",
                    "notice_supplier_name", "notice_id", "notice_live", "similarity_ratio",
                    "auditor_decision", "row_ids"])
        for _, r in pop[pop.match_status.str.startswith("candidate")].sort_values(
                ["annualised_estimate", "supplier_norm"], ascending=[False, True]).iterrows():
            for kind, n, ratio in matches[r.supplier_norm][1]:
                for _, c in cs[cs.supplier_norm == n].iterrows():
                    w.writerow([r.supplier_norm, kind, f"{r.annualised_estimate:.2f}", n,
                                c.supplier_name, c.notice_id, c.live_in_window, ratio, "",
                                r.row_ids])
    _ = title

    def block(d):
        tot = d.annualised_estimate.sum()

        def part(mask):
            x = d[mask]
            return {"count": int(len(x)), "annualised_estimate_gbp": r2(x.annualised_estimate.sum()),
                    "window_total_gbp": r2(x.window_total.sum()),
                    "share_of_population_annualised_estimate": r2(x.annualised_estimate.sum() / tot) if tot else None}
        return {"population": part(d.supplier_norm == d.supplier_norm),
                "exact_match_any_notice": part(d.match_status == "exact_match"),
                "exact_match_live_notice": part(d.exact_live),
                "candidates": part(d.match_status.str.startswith("candidate")),
                "no_notice_found": part(d.match_status == "no_notice_found")}
    e["counts"] = {"overall": block(pop),
                   "key_tags": {k: block(pop[pop.main_tag == k]) for k in KEY_TAGS},
                   "matched": int((pop.match_status == "exact_match").sum()),
                   "candidates": int(pop.match_status.str.startswith("candidate").sum()),
                   "flagged_no_notice_found": int((pop.match_status == "no_notice_found").sum())}
    fl = pop[pop.match_status == "no_notice_found"]
    e["totals_gbp"] = {"flagged_window_total": r2(fl.window_total.sum()),
                       "flagged_annualised_estimate": r2(fl.annualised_estimate.sum()),
                       "population_annualised_estimate": r2(pop.annualised_estimate.sum())}
    e["by_tag"] = {k: block(pop[pop.main_tag == k]) for k in TAGS}
    for k in TAGS:
        sub = fl[fl.main_tag == k]
        e["by_tag"][k].update({"count": int(len(sub)), "total_gbp": r2(sub.window_total.sum())})
    fields = ["supplier_norm", "main_tag", "window_total", "annualised_estimate", "n_payments",
              "match_status"]
    e["top_20"], e["top_5_by_tag"] = tops(fl, "annualised_estimate", "supplier_norm", fields, "main_tag")
    e["candidates_list"] = "outputs/analytics-full/off_contract_candidates.csv"
    e["caveats"] = cont["caveats"] + [PLACEMENT_CAVEAT,
                                      "Candidates (trading-name or similar-name) are for the "
                                      "auditor to confirm or reject and are never counted as matched.",
                                      "annualised_estimate = window total x annualisation_factor; "
                                      "an estimate, not a contract value."]
    return e, pop


def duplicates(df):
    W = METHOD_PARAMETERS["duplicate_window_days"]
    e = entry(description=f"Pairs of payments to one supplier for the same amount within "
              f"{W} days; a payment-accuracy risk indicator to investigate.",
              parameters={"duplicate_window_days": W}, name="duplicates")
    e["rule_ids"] = []
    e["rule_note"] = "no specific rule; payment accuracy indicator"
    pairs = []
    for (sn, amt), g in df.groupby(["supplier_norm", "amount"], sort=True):
        if len(g) < 2:
            continue
        g = g.sort_values(["date", "timestamp", "row_id"]).reset_index(drop=True)
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                dd = (g.date[j] - g.date[i]).days
                if dd > W:
                    break
                pairs.append({"supplier_norm": sn, "amount": amt,
                              "row_id_a": g.row_id[i], "row_id_b": g.row_id[j],
                              "date_a": str(g.date[i]), "date_b": str(g.date[j]),
                              "days_apart": dd,
                              "class": "same_timestamp" if g.timestamp[i] == g.timestamp[j]
                              else "different_timestamp",
                              "tag": g.tag[i]})
    pdf = pd.DataFrame(pairs, columns=["supplier_norm", "amount", "row_id_a", "row_id_b", "date_a",
                                       "date_b", "days_apart", "class", "tag"])
    uf = UF()
    for _, p in pdf.iterrows():
        uf.union(p.row_id_a, p.row_id_b)
    pdf["cluster_id"] = [uf.find(a) for a in pdf.row_id_a]
    cid_map = {c: f"C{i + 1:05d}" for i, c in enumerate(sorted(set(pdf.cluster_id)))}
    pdf["cluster_id"] = pdf.cluster_id.map(cid_map)
    pdf["row_ids"] = pdf.row_id_a + ";" + pdf.row_id_b
    pdf.sort_values(["amount", "row_id_a", "row_id_b"], ascending=[False, True, True]).to_csv(
        os.path.join(FULL, "duplicates.csv"), index=False)
    clusters = []
    for cid, g in pdf.groupby("cluster_id"):
        rows = sorted(set(g.row_id_a) | set(g.row_id_b))
        clusters.append({"cluster_id": cid, "supplier_norm": g.supplier_norm.iloc[0],
                         "amount": g.amount.iloc[0], "n_rows": len(rows), "n_pairs": len(g),
                         "classes": ";".join(sorted(set(g["class"]))), "tag": g.tag.iloc[0],
                         "repeat_value_beyond_first": g.amount.iloc[0] * (len(rows) - 1),
                         "row_ids": ";".join(rows)})
    cdf = pd.DataFrame(clusters, columns=["cluster_id", "supplier_norm", "amount", "n_rows", "n_pairs",
                                          "classes", "tag", "repeat_value_beyond_first", "row_ids"])
    cdf.sort_values(["repeat_value_beyond_first", "cluster_id"], ascending=[False, True]).to_csv(
        os.path.join(FULL, "duplicates_clusters.csv"), index=False)
    cls = {}
    for c in ["same_timestamp", "different_timestamp"]:
        x = pdf[pdf["class"] == c]
        xc = cdf[cdf.classes.str.contains(c)]
        cls[c] = {"pairs": int(len(x)), "pairs_amount_gbp": r2(x.amount.sum()),
                  "distinct_rows": int(len(set(x.row_id_a) | set(x.row_id_b))),
                  "clusters_containing_class": int(len(xc))}
    e["counts"] = {"pairs": int(len(pdf)), "clusters": int(len(cdf)),
                   "clusters_only_same_timestamp": int((cdf.classes == "same_timestamp").sum()),
                   "clusters_with_different_timestamp": int(cdf.classes.str.contains("different").sum()),
                   "by_class": cls}
    diff = pdf[pdf["class"] == "different_timestamp"]
    dcl = cdf[cdf.classes.str.contains("different")]
    e["totals_gbp"] = {"different_timestamp_pairs_amount": cls["different_timestamp"]["pairs_amount_gbp"],
                       "same_timestamp_pairs_amount": cls["same_timestamp"]["pairs_amount_gbp"],
                       "repeat_value_beyond_first_clusters_with_different_timestamp":
                           r2(dcl.repeat_value_beyond_first.sum()),
                       "repeat_value_beyond_first_all_clusters": r2(cdf.repeat_value_beyond_first.sum())}
    e["by_tag"] = by_tag(diff)
    e["by_tag_same_timestamp"] = by_tag(pdf[pdf["class"] == "same_timestamp"])
    fields = ["row_id_a", "row_id_b", "supplier_norm", "amount", "date_a", "date_b", "days_apart",
              "class", "tag", "cluster_id"]
    e["top_20"], e["top_5_by_tag"] = tops(diff.assign(_k=diff.row_id_a), "amount", "_k", fields)
    e["clusters_list"] = "outputs/analytics-full/duplicates_clusters.csv"
    e["caveats"] = ["same_timestamp pairs are probably lines of one payment run and are reported "
                    "separately; top_20 uses different_timestamp pairs only.",
                    "Recurring fixed-rate payments (e.g. weekly care) can repeat legitimately; "
                    "pairs are indicators to investigate."]
    return e


def expired_notice_spend(sup, cs, matches, window_start, cont):
    e = entry(description="Suppliers paid in the window whose every exact-matched notice ended "
              "before the window start; a risk indicator to investigate for spend after "
              "expiry without a recorded extension.", rule_ids=["CPR-58"],
              parameters={"window_start": window_start, "matching": "exact_match only"},
              name="expired_notice_spend")
    rows = []
    for _, s in sup.iterrows():
        if matches[s.supplier_norm][0] != "exact_match":
            continue
        n = cs[cs.supplier_norm == s.supplier_norm]
        ends = n.contract_end
        if (ends == "").any():
            continue
        if all(x < window_start for x in ends):
            last = n.sort_values(["contract_end", "notice_id"]).iloc[-1]
            rows.append({"supplier_norm": s.supplier_norm, "main_tag": s.main_tag,
                         "last_notice_id": last.notice_id, "last_notice_end": last.contract_end,
                         "n_notices": int(n.notice_id.nunique()), "window_total": s.window_total,
                         "n_payments": s.n_payments, "row_ids": s.row_ids})
    fl = pd.DataFrame(rows, columns=["supplier_norm", "main_tag", "last_notice_id", "last_notice_end",
                                     "n_notices", "window_total", "n_payments", "row_ids"])
    fl.sort_values(["window_total", "supplier_norm"], ascending=[False, True]).to_csv(
        os.path.join(FULL, "expired_notice_spend.csv"), index=False)
    e["counts"] = {"exact_matched_suppliers_paid": int(sum(1 for s in sup.supplier_norm
                                                            if matches[s][0] == "exact_match")),
                   "flagged": int(len(fl))}
    e["totals_gbp"] = {"flagged_window_total": r2(fl.window_total.sum() if len(fl) else 0)}
    e["by_tag"] = by_tag(fl, "window_total", "main_tag")
    e["top_20"], e["top_5_by_tag"] = tops(fl, "window_total", "supplier_norm",
                                          ["supplier_norm", "main_tag", "last_notice_id",
                                           "last_notice_end", "window_total", "n_payments"], "main_tag")
    e["caveats"] = ["A newer contract or an approved extension may exist with no notice."] + cont["caveats"]
    return e


def spend_vs_award(sup, cs, matches, factor):
    ratio_flag = METHOD_PARAMETERS["spend_vs_award_flag_ratio"]
    e = entry(description="Suppliers matched to one live single-supplier notice whose "
              "annualised_estimate is at least the flag ratio times the award per year; a "
              "risk indicator to request variation approvals.", rule_ids=["CPR-59", "CPR-60"],
              parameters={"spend_vs_award_flag_ratio": ratio_flag, "annualisation_factor": factor,
                          "contract_years": "(contract_end - contract_start).days / 365.25"},
              name="spend_vs_award")
    steps = {"exact_matched_suppliers": 0, "excluded_no_live_notice": 0,
             "excluded_more_than_one_live_notice": 0, "excluded_multi_supplier_notice": 0,
             "excluded_awarded_value_zero_or_blank": 0, "excluded_invalid_contract_dates": 0,
             "eligible": 0}
    live = cs[cs.live_in_window.astype(str) == "True"]
    rows = []
    for _, s in sup.iterrows():
        if matches[s.supplier_norm][0] != "exact_match":
            continue
        steps["exact_matched_suppliers"] += 1
        n = live[live.supplier_norm == s.supplier_norm]
        ids = sorted(set(n.notice_id))
        if not ids:
            steps["excluded_no_live_notice"] += 1
            continue
        if len(ids) > 1:
            steps["excluded_more_than_one_live_notice"] += 1
            continue
        c = n.iloc[0]
        if int(c.n_suppliers_on_notice) != 1:
            steps["excluded_multi_supplier_notice"] += 1
            continue
        if c.awarded_value == "" or not float(c.awarded_value) > 0:
            steps["excluded_awarded_value_zero_or_blank"] += 1
            continue
        if not c.contract_start or not c.contract_end or c.contract_end <= c.contract_start:
            steps["excluded_invalid_contract_dates"] += 1
            continue
        steps["eligible"] += 1
        yrs = (date.fromisoformat(c.contract_end) - date.fromisoformat(c.contract_start)).days / 365.25
        apy = float(c.awarded_value) / yrs
        ratio = s.annualised_estimate / apy
        rows.append({"supplier_norm": s.supplier_norm, "main_tag": s.main_tag, "notice_id": c.notice_id,
                     "awarded_value": float(c.awarded_value), "contract_start": c.contract_start,
                     "contract_end": c.contract_end, "contract_years": yrs, "award_per_year": apy,
                     "window_total": s.window_total, "annualised_estimate": s.annualised_estimate,
                     "ratio": ratio, "flagged": ratio >= ratio_flag, "row_ids": s.row_ids})
    df = pd.DataFrame(rows, columns=["supplier_norm", "main_tag", "notice_id", "awarded_value",
                                     "contract_start", "contract_end", "contract_years", "award_per_year",
                                     "window_total", "annualised_estimate", "ratio", "flagged", "row_ids"])
    df.sort_values(["annualised_estimate", "supplier_norm"], ascending=[False, True]).to_csv(
        os.path.join(FULL, "spend_vs_award.csv"), index=False)
    fl = df[df.flagged]
    e["counts"] = {"eligibility_steps": steps, "population": int(len(df)), "flagged": int(len(fl))}
    e["totals_gbp"] = {"flagged_window_total": r2(fl.window_total.sum() if len(fl) else 0),
                       "flagged_annualised_estimate": r2(fl.annualised_estimate.sum() if len(fl) else 0)}
    e["by_tag"] = by_tag(fl, "window_total", "main_tag")
    e["top_20"], e["top_5_by_tag"] = tops(fl, "annualised_estimate", "supplier_norm",
                                          ["supplier_norm", "main_tag", "notice_id", "awarded_value",
                                           "contract_years", "award_per_year", "annualised_estimate",
                                           "ratio"], "main_tag")
    e["caveats"] = ["Awarded values may be estimates or maxima; a ratio above 1.25 is an indicator "
                    "to request variation approvals, not a finding."]
    return e


def high_value_suppliers(sup, tiers, factor, matches, contracts_ok):
    t = next(x for x in tiers if x["tier"] == "three_quotes_and_notice")
    nt = next((x for x in tiers if x["tier"] == "notice_publication"), {"rule_ids": []})
    T, inc = t["value"], t["lower_edge_inclusive"]
    rids = t["rule_ids"] + nt["rule_ids"] + ["CPR-44", "CPR-45", "CPR-46", "CPR-47"]
    e = entry(description="Suppliers whose annualised_estimate enters the three-quotes tier: the "
              "population to request contract evidence for (contract, quotes, award approval), "
              "not a list of exceptions.", rule_ids=rids,
              parameters={"T": T, "lower_edge_inclusive": inc, "annualisation_factor": factor},
              name="high_value_suppliers")
    pop = sup[sup.annualised_estimate.map(lambda a: enters_tier(a, T, inc))].copy()
    pop["window_total_enters_tier"] = pop.window_total.map(lambda a: enters_tier(a, T, inc))
    pop["match_status"] = pop.supplier_norm.map(lambda s: matches[s][0]) if contracts_ok else None
    cols = ["supplier_norm", "raw_spellings", "main_tag", "tag_mix", "window_total",
            "annualised_estimate", "window_total_enters_tier", "n_payments", "services",
            "match_status", "row_ids"]
    pop.sort_values(["annualised_estimate", "supplier_norm"], ascending=[False, True])[cols].to_csv(
        os.path.join(FULL, "high_value_suppliers.csv"), index=False)
    e["counts"] = {"suppliers": int(len(pop)),
                   "window_total_enters_tier": int(pop.window_total_enters_tier.sum()),
                   "by_match_status": pop.match_status.value_counts().to_dict() if contracts_ok else None}
    e["totals_gbp"] = {"window_total": r2(pop.window_total.sum()),
                       "annualised_estimate": r2(pop.annualised_estimate.sum())}
    e["by_tag"] = by_tag(pop, "window_total", "main_tag")
    e["top_20"], e["top_5_by_tag"] = tops(pop, "annualised_estimate", "supplier_norm",
                                          ["supplier_norm", "main_tag", "window_total",
                                           "annualised_estimate", "window_total_enters_tier",
                                           "n_payments", "match_status"], "main_tag")
    e["caveats"] = ["annualised_estimate = window total x annualisation_factor; an estimate, "
                    "not a contract value.", "This is a sampling population, not a list of exceptions."]
    return e


def skipped(name, reason, desc, rule_ids):
    e = entry(status="skipped", reason=reason, description=desc, rule_ids=rule_ids, name=name)
    e["full_list"] = None
    return e


def main():
    rules = load_rules()
    tiers, skipped_tiers = load_tiers(rules)
    Ts = testing_thresholds(tiers)
    with open(os.path.join(FULL, "clean_summary.json")) as f:
        cl = json.load(f)
    with open(os.path.join(FULL, "contracts_summary.json")) as f:
        cont = json.load(f)
    factor = cl["window"]["annualisation_factor"]
    window_start = cl["window"]["start"]
    df = load_spend()
    floor = df.amount.min()
    sup = supplier_table(df, factor)
    contracts_ok = cont.get("status") == "ran"

    tests = {}
    tests["threshold_clustering"] = threshold_clustering(df, Ts, floor)
    tests["split_purchases"] = split_purchases(df, Ts)
    matches = {}
    if contracts_ok:
        cs = pd.read_csv(os.path.join(FULL, "contract_suppliers.csv"), dtype=str, keep_default_na=False)
        matches = match_suppliers(sup.supplier_norm, cs)
        tests["off_contract"], _ = off_contract(sup, cs, tiers, factor, cont, matches)
    else:
        tests["off_contract"] = skipped("off_contract", cont.get("reason"),
                                        "Suppliers above the notice tier with no notice found.",
                                        ["CPR-50", "CPR-05"])
    tests["duplicates"] = duplicates(df)
    if contracts_ok:
        tests["expired_notice_spend"] = expired_notice_spend(sup, cs, matches, window_start, cont)
        tests["spend_vs_award"] = spend_vs_award(sup, cs, matches, factor)
    else:
        tests["expired_notice_spend"] = skipped("expired_notice_spend", cont.get("reason"),
                                                "Spend after notice expiry.", ["CPR-58"])
        tests["spend_vs_award"] = skipped("spend_vs_award", cont.get("reason"),
                                          "Spend compared with award per year.", ["CPR-59", "CPR-60"])
    tests["high_value_suppliers"] = high_value_suppliers(sup, tiers, factor, matches, contracts_ok)

    mp = {k: {"value": v, "source": "CLAUDE.md"} for k, v in METHOD_PARAMETERS.items()}
    mp["annualisation_factor"] = {"value": factor, "source": "CLAUDE.md",
                                  "derivation": f"12 / {cl['window']['months']} monthly workbooks",
                                  "label": "annualised_estimate"}
    mp["contracts_finder_export_row_cap"] = {"value": CONTRACTS_FINDER_EXPORT_ROW_CAP,
                                             "source": "CLAUDE.md",
                                             "note": "row count, not money"}
    mp["name_similarity_ratio"] = {"value": SIMILARITY_RATIO, "source": "spend-analyst definition"}
    mp["name_containment_min_chars"] = {"value": CONTAINMENT_MIN_CHARS, "source": "spend-analyst definition"}
    out = {
        "generated_on": date.today().isoformat(),
        "generated_by": "scripts/run_all.py",
        "inputs": {"spend_files": [{k: f[k] for k in ["file", "sha256", "header_excel_row", "rows",
                                                      "date_min", "date_max"]} for f in cl["spend_files"]],
                   "rules_json": {"path": "outputs/rules.json", "sha256": sha256(RULES_JSON)},
                   "contracts_csv": {"present": os.path.exists(CONTRACTS_CSV),
                                     "sha256": sha256(CONTRACTS_CSV) if os.path.exists(CONTRACTS_CSV) else None,
                                     "status": cont.get("status"), "reason": cont.get("reason")}},
        "window": cl["window"],
        "thresholds": {"tiers": tiers, "skipped": skipped_tiers, "testing_thresholds": Ts},
        "method_parameters": mp,
        "cleaning": {"rows_read": cl["rows_read"], "excluded": cl["excluded"],
                     "rows_tested": cl["rows_tested"], "total_tested_gbp": cl["total_tested_gbp"],
                     "by_tag": cl["by_tag"], "per_file": [
                         {k: f[k] for k in ["file", "rows", "kept_rows", "excluded_rows", "raw_gbp",
                                            "kept_gbp", "excluded_gbp", "excluded_by_reason"]}
                         for f in cl["spend_files"]],
                     "cross_file_duplicate_rows": cl["cross_file_duplicate_rows"],
                     "same_timestamp_dup_rows_within_file": cl["same_timestamp_dup_rows_within_file"],
                     "blank_category_rows_read": cl["blank_category_rows_read"],
                     "distinct_supplier_strings": cl["distinct_supplier_strings"],
                     "distinct_supplier_norm_tested": int(sup.shape[0]),
                     "unseen_values": cl["unseen_values"],
                     "logs": ["outputs/analytics-full/exclusions.csv",
                              "outputs/analytics-full/tag_mapping.csv"]},
        "contracts": ({"present": True, "kept": cont["kept"], "dropped": cont["dropped"],
                       "organisation_names_kept": cont["organisation_names_kept"],
                       "organisation_names_dropped": cont["organisation_names_dropped"],
                       "per_publication_year": cont["per_publication_year"],
                       "live_in_window": cont["live_in_window"],
                       "distinct_supplier_norm": cont["distinct_supplier_norm"],
                       "distinct_supplier_norm_live": cont["distinct_supplier_norm_live"],
                       "supplier_blocks": cont["supplier_blocks"],
                       "notices_with_multiple_suppliers": cont["notices_with_multiple_suppliers"],
                       "companies_house_join": cont["companies_house_join"],
                       "data_quality": cont["data_quality"], "warnings": cont["warnings"],
                       "caveats": cont["caveats"]} if contracts_ok else
                      {"present": cont.get("present"), "status": "skipped", "reason": cont.get("reason"),
                       "companies_house_join": "not available: spend data has no Companies House number"}),
        "tests": tests,
        "self_check": {"status": "pending"},
        "language": LANGUAGE,
    }
    write_json(ANALYTICS_JSON, out)
    for k, v in tests.items():
        c = v["counts"]
        brief = {kk: vv for kk, vv in c.items() if not isinstance(vv, dict)}
        print(f"{k}: {v['status']} {brief} totals={v['totals_gbp']}")


if __name__ == "__main__":
    main()
