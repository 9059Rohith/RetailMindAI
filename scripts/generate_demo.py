"""Regenerate the committed lightweight demo CSV deterministically."""
from pathlib import Path

from retailmind.data import generate_retail_data


def main() -> None:
    destination = Path("data/demo_sales.csv")
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = generate_retail_data(products=12, stores=4, days=120, seed=42)
    data.to_csv(destination, index=False)
    print(f"Wrote {len(data):,} rows to {destination}")


if __name__ == "__main__":
    main()
