"""Main entry point for Policy SQL Dataset generation."""

from pathlib import Path

from tqdm import tqdm

from .gold_generator import generate_gold_label
from .negative_generator import generate_negative
from .output_writer import format_record, write_dataset
from .policy_assigner import generate_all_policies, print_policy_stats
from .qa_checker import print_qa_report, run_qa_check, save_qa_report
from .rewriter import rewrite
from .role_extractor import extract_roles
from .spider_loader import load_examples, load_schemas
from .violation_checker import check_violations


def process_split(
    examples: list,
    schemas: dict,
    all_policies: dict,
    split: str,
) -> list[dict]:
    """Process a single split (train/dev/test)."""
    records = []

    for idx, example in enumerate(tqdm(examples, desc=f"Processing {split}")):
        db_id = example.db_id
        schema = schemas[db_id]
        policies = all_policies.get(db_id, {})

        # Extract column references and their roles
        refs = extract_roles(example.sql, schema)

        # Check for violations
        violations = check_violations(refs, policies)

        # Attempt rewrite if violations exist
        rewrite_result = None
        if violations:
            rewrite_result = rewrite(example.query, violations, schema, policies)

        # Generate gold label
        gold_label = generate_gold_label(example, violations, rewrite_result)

        # Generate negative examples
        negative_examples = generate_negative(example.query, example.sql, policies, schema)

        # Format and collect record
        record_id = f"{split}_{idx:05d}"
        record = format_record(
            record_id=record_id,
            db_id=db_id,
            question=example.question,
            original_sql=example.query,
            column_policies=policies,
            violations_original=violations,
            gold_label=gold_label,
            negative_examples=negative_examples,
        )
        records.append(record)

    return records


def main(
    spider_path: str | Path = "spider_data/spider_data",
    output_path: str | Path = "data",
    overrides_path: str | Path | None = None,
) -> None:
    """Main entry point."""
    spider_path = Path(spider_path)
    output_path = Path(output_path)

    print("=" * 60)
    print("Policy SQL Dataset Generator")
    print("=" * 60)

    # Step 1: Load schemas
    print("\n[1/6] Loading schemas...")
    schemas = load_schemas(spider_path / "tables.json")
    print(f"  Loaded {len(schemas)} database schemas")

    # Step 2: Generate policies
    print("\n[2/6] Generating policies...")
    all_policies = generate_all_policies(
        schemas, output_path / "policies", overrides_path
    )
    print_policy_stats(schemas, all_policies)

    # Step 3: Load and process train data
    print("\n[3/6] Processing train data...")
    train_examples = load_examples(spider_path / "train_spider.json")
    train_records = process_split(train_examples, schemas, all_policies, "train")

    # Step 4: Load and process dev data
    print("\n[4/6] Processing dev data...")
    dev_examples = load_examples(spider_path / "dev.json")
    dev_records = process_split(dev_examples, schemas, all_policies, "dev")

    # Step 5: Write outputs
    print("\n[5/6] Writing outputs...")
    write_dataset(train_records, output_path, "train")
    write_dataset(dev_records, output_path, "dev")

    # Note: test.json in Spider doesn't have SQL field, skip for now
    # test_examples = load_examples(spider_path / "test.json")

    # Step 6: Run QA checks
    print("\n[6/6] Running QA checks...")
    reports = []
    for split in ["train", "dev"]:
        report = run_qa_check(output_path, split)
        print_qa_report(report)
        reports.append(report)

    save_qa_report(reports, output_path)

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
