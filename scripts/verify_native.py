"""Exercise public setup/plan/version/check commands with the admitted language tools."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "python": ("src/subject.py", "add_one", "tests/test_subject.py", "assert add_one(1) == 2", "add_one(1)"),
    "typescript": ("src/value.ts", "isEven", "test/value.test.ts", "assert.equal(isEven(2), true); assert.equal(isEven(3), false);", "isEven(2); isEven(3);"),
    "java": ("src/main/java/demo/Flag.java", "enabled", "src/test/java/demo/FlagTest.java", "assertTrue(new Flag().enabled());", "new Flag().enabled();"),
}


def invoke(folder, command, arguments, expected=0):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")
    completed = subprocess.run([sys.executable, "-B", "-m", "sentinel", command, *arguments], env=env, capture_output=True)
    name = command + "-" + str(len(list(folder.glob("*.json"))))
    (folder / (name + ".json")).write_bytes(completed.stdout)
    (folder / (name + ".stderr")).write_bytes(completed.stderr)
    payload = json.loads(completed.stdout)
    assert completed.returncode == payload["exitCode"] == expected, (payload, completed.stderr.decode(errors="replace"))
    return payload


def verify(language, output):
    folder = output / language
    folder.mkdir(parents=True)
    admissions = json.loads((ROOT / "src/sentinel/admission.json").read_text())["admitted"]
    entry = max((item for item in admissions if item["language"] == language),
                key=lambda item: tuple(map(int, item["toolVersion"].split("."))))
    sources = folder / "sources"
    sources.mkdir()
    repository = sources / entry["source"]["repository"].split("/")[-1]
    subprocess.run(["git", "clone", "--quiet", "https://github.com/" + entry["source"]["repository"] + ".git", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "checkout", "--quiet", entry["source"]["commit"]], check=True)
    project = folder / "project"
    shutil.copytree(ROOT / "tests/fixtures/native" / language, project)
    original = {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()}
    common = ["--project", str(project), "--tools", str(folder / "tools")]
    options = ["--sources", str(sources), "--language", language]
    if language == "java":
        options.append("--java-dependencies")
    print(language + ": setup", flush=True)
    setup = invoke(folder, "setup", [*common, *options])
    assert setup["results"][0]["status"] == "installed", setup
    assert invoke(folder, "plan", common)["results"][0]["status"] == "planned"
    version_payload = invoke(folder, "version", common)
    assert version_payload["command"] == "version", version_payload
    version = version_payload["results"][0]
    assert version["status"] == "ready" and version["admitted"] is True, version
    source, function, test, strong, weak = TARGETS[language]
    selection = ["--file", source, "--function", function, "--tests", test]
    selected = invoke(folder, "check", [*common, *selection])
    result = selected["results"][0]
    assert selected["selection"] == "partial" and result["status"] == "passed", selected
    assert result["details"]["scope"]["files"] == [source], result
    assert result["details"]["scope"]["tests"] == [test], result
    assert len(result["details"]["crap"]["functions"]) == 1, result
    assert result["details"]["mutation"]["inScope"] > 0, result
    print(language + ": selected check passed", flush=True)
    test_path = project / test
    text = test_path.read_text()
    assert strong in text
    test_path.write_text(text.replace(strong, weak))
    failed = invoke(folder, "check", [*common, *selection], expected=2)
    assert failed["results"][0]["status"] == "qualityFailed", failed
    assert failed["results"][0]["details"]["mutation"]["pass"] is False, failed
    test_path.write_bytes(original[Path(test)])
    full = invoke(folder, "check", [*common, "--all"])
    assert full["selection"] == "allConfigured" and full["results"][0]["status"] == "passed", full
    assert all((project / path).read_bytes() == data for path, data in original.items())
    print(language + ": weak tests rejected; restored full check passed", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--language", choices=tuple(TARGETS), action="append")
    args = parser.parse_args()
    for language in args.language or TARGETS:
        verify(language, args.output.resolve())
