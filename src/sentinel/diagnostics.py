"""Normalize measured facts, without generating explanations or repair advice."""

from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction


STATES = ("killed", "survived", "uncovered", "timedOut", "compileError", "runtimeError", "pending", "ignored", "toolError")


def _display_score(value, suffix=""):
    return "미측정" if value is None else str(value) + suffix


def text_details(details):
    crap, mutation = details["crap"], details["mutation"]
    lines = [f"  CRAP max={_display_score(crap['maxScore'])} (limit={crap['limit']})",
             f"  mutation={_display_score(mutation['score'], '%')} ({mutation['counts']['killed']}/{mutation['inScope']}, minimum={mutation['minimum']}%)"]
    for item in crap["functions"]:
        lines.append(f"  {item.get('file', '?')}:{item.get('line', '?')} {item.get('function', item['id'])}: CRAP={_display_score(item['score'])}")
    for item in mutation["functions"]:
        lines.append(f"  {item['file']} {item['function']}: mutation={_display_score(item['score'], '%')} ({item['killed']}/{item['inScope']})")
    failures = [item for item in mutation["mutants"] if item["status"] != "killed"]
    for item in failures[:20]:
        lines.append(f"  {item.get('file', '?')}:{item.get('line', '?')} {item['status']} [{item['id']}]")
    if len(failures) > 20:
        lines.append(f"  +{len(failures) - 20} mutant results; use --format json for all measured facts")
    return lines


def _percent(killed, total):
    if total == 0:
        return None
    with localcontext() as context:
        context.prec = 40
        return format(Decimal(killed * 100) / Decimal(total), ".12f").rstrip("0").rstrip(".")


def _group_mutants(mutants, keys, minimum):
    groups = {}
    for mutant in mutants:
        identity = tuple(mutant.get(key) for key in keys)
        if any(value is None for value in identity):
            continue
        groups.setdefault(identity, []).append(mutant)
    output = []
    for identity, rows in sorted(groups.items()):
        counts = Counter(row["status"] for row in rows)
        output.append({**dict(zip(keys, identity)), "inScope": len(rows), "killed": counts["killed"],
                       "score": _percent(counts["killed"], len(rows)),
                       "pass": Fraction(counts["killed"] * 100, len(rows)) >= Fraction(minimum),
                       "counts": {state: counts[state] for state in STATES}})
    return output


def _include_zero_groups(groups, functions, keys):
    present = {tuple(group[key] for key in keys) for group in groups}
    for function in functions:
        identity = tuple(function.get(key) for key in keys)
        if None in identity or identity in present:
            continue
        groups.append({**dict(zip(keys, identity)), "inScope": 0, "killed": 0, "score": None,
                       "pass": None, "reason": "zeroMutants", "counts": dict.fromkeys(STATES, 0)})
        present.add(identity)
    return sorted(groups, key=lambda group: tuple(group[key] for key in keys))


def normalize_details(language, raw, gate):
    if not raw or "crap" not in raw or "mutation" not in raw:
        raise ValueError("qualityDetailsMissing")
    crap = raw["crap"]
    mutation = raw["mutation"]
    if language == "python":
        functions = [{"file": row["moduleRelativePath"], "function": row["qualifiedName"], "id": row["callableId"],
                      "line": row.get("line"), "sourceRange": row["sourceRange"],
                      "score": row["crapRaw"], "complexity": row["cyclomaticComplexity"],
                      "coveredUnits": row["coveredUnits"], "totalUnits": row["totalUnits"],
                      "coverageBasis": row["coverageBasis"], "status": row["status"]} for row in crap["callables"]]
        mutants = raw.get("mutationDetails", {}).get("mutants", [])
        counts = mutation["counts"]
        crap_pass = crap["pass"]
    elif language == "typescript":
        functions = [{"file": row.get("file"), "function": row.get("function"), "id": row["id"],
                      "sourceRange": row.get("sourceRange"), "line": row.get("line"), "score": row["decimal"],
                      "complexity": row.get("complexity"), "coverage": row.get("coverage"),
                      "coverageBasis": row.get("coverageBasis"), "status": "passed" if row["pass"] else "crapThresholdExceeded"} for row in crap["rows"]]
        functions += crap.get("unknownDetails", [{"id": identifier, "score": None, "status": "coverageUnknown"} for identifier in crap["unknown"]])
        mutants = [{**row, "file": row.get("modulePath"), "line": row.get("location", {}).get("start", {}).get("line")} for row in mutation["results"]]
        mutation = mutation["gate"]
        counts = mutation["counts"]
        crap_pass = crap["pass"]
    elif language == "java":
        functions = crap["functions"]
        mutants = mutation["mutants"]
        counts = {state: mutation[state] for state in STATES}
        crap_pass = crap["passed"]
    else:
        raise ValueError("qualityDetailsUnsupported")
    total = mutation["inScope"]
    if type(total) is not int or total < 0 or type(mutation["pass"]) is not bool or type(crap_pass) is not bool:
        raise ValueError("qualityVerdictInvalid")
    if any(type(counts[state]) is not int or counts[state] < 0 for state in STATES) or sum(counts.values()) != total:
        raise ValueError("mutationCountsInvalid")
    if len(mutants) != total or len({row["id"] for row in mutants}) != total:
        raise ValueError("mutationDetailsIncomplete")
    if Counter(row["status"] for row in mutants) != Counter({state: value for state, value in counts.items() if value}):
        raise ValueError("mutationDetailsMismatch")
    expected_pass = total > 0 and Fraction(counts["killed"] * 100, total) >= Fraction(gate["mutationMin"]) and mutation.get("unauthorizedExclusion", 0) == 0
    if mutation["pass"] != expected_pass:
        raise ValueError("mutationVerdictMismatch")
    scores = [row["score"] for row in functions if row.get("score") is not None]
    maximum = max(scores, key=Fraction) if scores else None
    file_rows = []
    for file in sorted({row["file"] for row in functions if row.get("file") is not None}):
        rows = [row for row in functions if row.get("file") == file]
        known = [row["score"] for row in rows if row.get("score") is not None]
        file_rows.append({"file": file, "functionCount": len(rows), "maxScore": max(known, key=Fraction) if known else None,
                          "unknownCount": sum(row.get("score") is None for row in rows)})
    return {"schemaVersion": "sentinel-diagnostics-v1", "scope": raw.get("scope", {}),
            "crap": {"limit": gate["crapMax"], "maxScore": maximum, "pass": crap_pass, "functions": functions, "files": file_rows},
            "mutation": {"minimum": gate["mutationMin"], "score": _percent(counts["killed"], total),
                         "inScope": total, "counts": counts, "pass": mutation["pass"], "mutants": mutants,
                         "files": _include_zero_groups(_group_mutants(mutants, ("file",), gate["mutationMin"]), functions, ("file",)),
                         "functions": _include_zero_groups(_group_mutants(mutants, ("file", "function"), gate["mutationMin"]), functions, ("file", "function"))}}
