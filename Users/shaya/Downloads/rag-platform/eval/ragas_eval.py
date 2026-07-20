"""
RAGAS evaluation script, meant to run in CI against a small fixed dataset
(eval/dataset.json) so a regression in retrieval or prompting is caught
before merge. Fails the build if scores drop below thresholds.
"""
import json
import sys
import requests
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

API_BASE = "http://localhost:8000/api/v1"
THRESHOLDS = {"faithfulness": 0.7, "answer_relevancy": 0.7, "context_precision": 0.6, "context_recall": 0.6}


def run_eval(project_id: str, token: str, dataset_path: str = "eval/dataset.json"):
    with open(dataset_path) as f:
        samples = json.load(f)

    questions, answers, contexts, ground_truths = [], [], [], []
    headers = {"Authorization": f"Bearer {token}"}

    for sample in samples:
        r = requests.post(f"{API_BASE}/projects/{project_id}/query",
                           json={"question": sample["question"]}, headers=headers)
        r.raise_for_status()
        data = r.json()
        questions.append(sample["question"])
        answers.append(data["answer"])
        contexts.append([s["text"] for s in data["sources"]])
        ground_truths.append(sample["ground_truth"])

    dataset = Dataset.from_dict({
        "question": questions, "answer": answers, "contexts": contexts, "ground_truth": ground_truths,
    })

    result = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision, context_recall])
    scores = result.to_pandas().mean(numeric_only=True).to_dict()
    print(json.dumps(scores, indent=2))

    failed = [name for name, threshold in THRESHOLDS.items() if scores.get(name, 0) < threshold]
    if failed:
        print(f"FAILED thresholds: {failed}")
        sys.exit(1)
    print("All RAGAS thresholds passed.")


if __name__ == "__main__":
    import os
    run_eval(project_id=os.environ["EVAL_PROJECT_ID"], token=os.environ["EVAL_TOKEN"])
