"""NCS Assessment Learner v0: offline, advisory research prototype.

Not imported by the grade compiler. No network, provider calls or user-facing
predictions. Trains only on caller-supplied aggregate feature rows.
"""
from __future__ import annotations
import math
from typing import Any

def _sigmoid(x: float) -> float:
    if x >= 0:
        z=math.exp(-x); return 1.0/(1.0+z)
    z=math.exp(x); return z/(1.0+z)

def fit_logistic_regression(rows: list[dict[str, Any]], feature_names: list[str], *, learning_rate: float=0.05, l2: float=0.1, iterations: int=1500) -> dict[str, Any]:
    if len(rows)<5 or not feature_names: raise ValueError("at least five rows and one feature are required")
    if len({r.get("subject_id") for r in rows})<5: raise ValueError("training rows must cover at least five distinct subjects")
    x=[]; y=[]
    for row in rows:
        label=row.get("label")
        if label not in (0,1): raise ValueError("labels must be binary 0/1")
        values=[row.get("features",{}).get(name) for name in feature_names]
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in values): raise ValueError("features must be finite numbers")
        x.append([float(v) for v in values]); y.append(float(label))
    means=[sum(row[j] for row in x)/len(x) for j in range(len(feature_names))]
    scales=[]
    for j,mean in enumerate(means):
        variance=sum((row[j]-mean)**2 for row in x)/len(x); scales.append(math.sqrt(variance) or 1.0)
    z=[[(row[j]-means[j])/scales[j] for j in range(len(feature_names))] for row in x]
    weights=[0.0]*len(feature_names); intercept=0.0
    for _ in range(iterations):
        grad_w=[0.0]*len(weights); grad_b=0.0
        for row,label in zip(z,y):
            p=_sigmoid(intercept+sum(w*v for w,v in zip(weights,row))); error=p-label; grad_b+=error
            for j,value in enumerate(row): grad_w[j]+=error*value
        n=len(rows); intercept-=learning_rate*grad_b/n
        weights=[w-learning_rate*(grad_w[j]/n+l2*w) for j,w in enumerate(weights)]
    return {"schema":"ncs-learner-v0-artifact/0.1","algorithm":"standardized-logistic-regression",
            "feature_names":feature_names,"means":means,"scales":scales,"weights":weights,"intercept":intercept,
            "training_subject_count":len({r["subject_id"] for r in rows}),"advisory_only":True,
            "grade_authority":False,"user_facing_predictions_enabled":False}

def predict_probability(artifact: dict[str, Any], features: dict[str,float]) -> float:
    if artifact.get("grade_authority") is not False or artifact.get("advisory_only") is not True: raise ValueError("untrusted learner artifact")
    values=[features.get(name) for name in artifact["feature_names"]]
    if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in values): raise ValueError("missing or invalid learner feature")
    normalized=[(float(v)-m)/s for v,m,s in zip(values,artifact["means"],artifact["scales"])]
    return _sigmoid(artifact["intercept"]+sum(w*v for w,v in zip(artifact["weights"],normalized)))

def brier_score(labels: list[int], probabilities: list[float]) -> float:
    if not labels or len(labels)!=len(probabilities): raise ValueError("labels and probabilities must be aligned")
    if any(y not in (0,1) for y in labels) or any(not 0<=p<=1 for p in probabilities): raise ValueError("invalid labels or probabilities")
    return sum((p-y)**2 for y,p in zip(labels,probabilities))/len(labels)

def roc_auc(labels: list[int], probabilities: list[float]) -> float | None:
    if len(labels)!=len(probabilities) or not labels: raise ValueError("labels and probabilities must be aligned")
    positives=sum(labels); negatives=len(labels)-positives
    if positives==0 or negatives==0: return None
    ordered=sorted(zip(probabilities,labels),key=lambda item:item[0]); rank_sum=0.0; i=0
    while i<len(ordered):
        j=i+1
        while j<len(ordered) and ordered[j][0]==ordered[i][0]: j+=1
        average_rank=((i+1)+j)/2; rank_sum+=average_rank*sum(label for _,label in ordered[i:j]); i=j
    return (rank_sum-positives*(positives+1)/2)/(positives*negatives)

def temporal_split(rows: list[dict[str,Any]], cutoff: str) -> tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    train=[r for r in rows if str(r.get("recorded_at",""))<cutoff]; test=[r for r in rows if str(r.get("recorded_at",""))>=cutoff]
    if not train or not test: raise ValueError("temporal split must produce non-empty train and test sets")
    return train,test

def learner_release_gate(*, distinct_configurations: int, distinct_families: int, temporal_validation_passed: bool) -> dict[str,Any]:
    ready=distinct_configurations>=15 and distinct_families>=4 and temporal_validation_passed is True
    return {"status":"ELIGIBLE_FOR_OFFLINE_VALIDATION" if ready else "INSUFFICIENT_DATA",
            "minimum_configurations":15,"minimum_families":4,"temporal_validation_required":True,
            "user_facing_predictions_enabled":False,"grade_authority":False}
