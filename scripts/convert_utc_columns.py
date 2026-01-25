"""Script to convert datetime columns containing [UTC] in their names.

Convert from non-standard format to ISO 8601 format.

Supports formats like: "M/D/YYYY, h:mm:ss.fff AM/PM"
Converts to ISO 8601: "YYYY-MM-DDTHH:mm:ss.fffZ"
"""

import argparse
import sys
import warnings

import pandas as pd

warnings.simplefilter(action="ignore", category=FutureWarning)


def convert_utc_columns(input_file, output_file=None):
  """Read a CSV file and convert all [UTC] columns to ISO 8601 format.

  Args:
    input_file (str): Path to input CSV file
    output_file (str): Path to output CSV file. If None, overwrites input file.
  """
  try:
    # Read the CSV file
    df = pd.read_csv(input_file)

    # Find columns with [UTC] in the name
    utc_columns = [col for col in df.columns if "[UTC]" in col]

    if not utc_columns:
      print(f"No columns with [UTC] found in {input_file}")
      return

    print(f"Found {len(utc_columns)} column(s) with [UTC]:")
    for col in utc_columns:
      print(f"  - {col}")

    # Convert each [UTC] column to ISO 8601 format
    for col in utc_columns:
      try:
        # Parse the datetime and convert to ISO 8601
        df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        print(f"✓ Converted: {col}")
      except Exception as e:
        print(f"✗ Error converting {col}: {e}")

    # Rename columns to remove [UTC] suffix
    df = rename_utc_columns(df)
    print("✓ Renamed columns to remove [UTC]")

    # Save the result
    output_path = output_file if output_file else input_file
    df.to_csv(output_path, index=False)
    print(f"\n✓ Successfully saved to: {output_path}")

  except FileNotFoundError:
    print(f"Error: File not found: {input_file}", file=sys.stderr)
    sys.exit(1)
  except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)


def rename_utc_columns(df):
  """Rename columns containing [UTC] to remove the [UTC] suffix.

  Args:
    df (pd.DataFrame): Input dataframe

  Returns:
    pd.DataFrame: Dataframe with renamed columns
  """
  # Find columns with [UTC] in the name
  utc_columns = [col for col in df.columns if "[UTC]" in col]

  if not utc_columns:
    return df

  # Create rename mapping by removing [UTC] and trailing spaces
  rename_mapping = {
    col: col.replace(" [UTC]", "").replace("[UTC]", "") for col in utc_columns
  }

  # Rename columns and return
  return df.rename(columns=rename_mapping)


def main():
  """Parse arguments and call conversion function."""
  parser = argparse.ArgumentParser(
    description="Convert [UTC] datetime columns to ISO 8601 format"
  )
  parser.add_argument("input_file", help="Path to input CSV file", type=str)
  parser.add_argument(
    "-o",
    "--output",
    help="Path to output CSV file (default: overwrites input file)",
    type=str,
  )

  args = parser.parse_args()

  # Confirm if overwriting the input file
  if not args.output:
    response = (
      input(f"No output file specified. Overwrite '{args.input_file}'? (y/n): ")
      .strip()
      .lower()
    )
    if response != "y":
      print("Operation cancelled.")
      sys.exit(0)

  convert_utc_columns(args.input_file, args.output)


if __name__ == "__main__":
  main()
