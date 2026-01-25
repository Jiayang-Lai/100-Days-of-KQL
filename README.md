# Introduction

This repository holds the dataset and the queries created for the 100 days of KQL challenge.

# Project Structure

There are two main folders in this repository:

- `samples`: holds the sample data used by the KQL queries. Microsoft has a great repository with a comprehensive list of sample log [here](https://github.com/Azure/Azure-Sentinel/tree/master/Sample%20Data).
- `days`: holds the KQL queries created each day.

# Setup

Instead of relying on Actual Sentinel instance or Azure Data Explorer, this project uses an ADX emulator, aka Kustainer. Please find more information from [Microsoft site](https://learn.microsoft.com/en-us/azure/data-explorer/kusto-emulator-overview). According to Microsoft:

> The Kusto emulator is a local environment that encapsulates the query engine. You can use the environment to facilitate local development and automated testing. Since the environment runs locally, it doesn't require provisioning Azure services or incurring any cost.

I have created a docker compose file based on the one from [Tao of Mac](https://taoofmac.com/space/blog/2024/06/28/2100) (thank you Taoofmac!), with the only change of using a minimal Jupyter notebook image rather than the PyTorch one.

To set up the local environment, simply run command `make up` (please make sure you have make installed), the Kustainer uses a volume for persistent storage but you have to manually load the data after each restart or new Kustainer container creation.

After the environment is up and running, run command `docker logs <your Jupyter container id>` to get the access URL with token. Then follow this [guide](https://learn.microsoft.com/en-us/azure-data-studio/notebooks/notebooks-kqlmagic) to install KqlMagic extension for Jupyter notebook. Here is the command (from Tao of Mac) to install KqlMagic and activate it:

```python
!pip install kqlmagic
%reload_ext Kqlmagic 
%kql --activate_kernel
```

To connect to the Kustainer, run this command:

```python
azureDataExplorer://anonymous;cluster='http://kusto:8080';database='NetDefaultDB';alias='default'
```

Vola, your local lab environment is now ready for KQl queries :).

Or is it?

When I tried the commands above, running KQL queries return an error of `KeyError: 'DEFAULT'`. After diving into [GitHub issues](https://github.com/microsoft/jupyter-Kqlmagic/issues/114) and posts, I found out that one of the dependencies (prettytable) has a breaking change that KqlMagic never accommodates. Therefore, as the comment in the issue suggests, we have to install an older version of prettytable by running command `!pip install kqlmagic==3.11.0` before running other installation command.

TL;DR: open a new notebook and run this command instead:

```python
!pip install prettytable==3.11.0
!pip install kqlmagic
%reload_ext Kqlmagic 
%kql --activate_kernel
%kql azureDataExplorer://anonymous;cluster='http://kusto:8080';database='NetDefaultDB';alias='default'
```

To destroy the environment, run `make down` (you have to specifically remove the volume after this command).

# 2026-01-20 Update

## KqlMagic prettytable Issue and PR

While working on the setup, I discovered that KqlMagic breaks due to breaking changes in the `prettytable` dependency. This causes the `KeyError: 'DEFAULT'` error mentioned in the Setup section. I have submitted a PR to address this issue: [microsoft/jupyter-Kqlmagic#121](https://github.com/microsoft/jupyter-Kqlmagic/pull/121). Until the PR is merged, the workaround of installing an older version of prettytable (`pip install prettytable==3.11.0`) is necessary.

# 2026-01-25 Update

## convert_utc_columns.py

When exporting query result from Azure portal, the columns with datetime type will be exported with a name suffix of ` [UTC]` and a non ISO8601 compliant datetime string in a csv file. This causes issues when using `externaldata` to import from this export. (Yes I know it is possible to query and export the data with the ISO8601 datetime string via [azure-monitor-query](https://pypi.org/project/azure-monitor-query/))

Therefore, I wrote a quick script for QoL automation.

Added a utility script `scripts/convert_utc_columns.py` to process CSV files with datetime columns that have `[UTC]` in their column names. The script performs two main operations:

1. **DateTime Conversion**: Converts non-standard datetime formats (e.g., `M/D/YYYY, h:mm:ss.fff AM/PM`) to ISO 8601 format (`YYYY-MM-DDTHH:MM:SS.fffZ`)
2. **Column Renaming**: Removes the `[UTC]` suffix from column names after conversion

**Usage:**
```bash
# Convert with output file
python3 scripts/convert_utc_columns.py samples/input.csv -o samples/output.csv

# Convert in-place (prompts for confirmation)
python3 scripts/convert_utc_columns.py samples/input.csv
```

**Features:**
- Automatically detects all columns containing `[UTC]` (**the space before the square bracket must be removed**) in their names
- Supports reusable functions for integration with other scripts:
  - `convert_utc_columns(input_file, output_file)`: File-based conversion
  - `rename_utc_columns(df)`: In-memory dataframe column renaming

Some sample files come from Tom's repository [here](https://github.com/tom564/100_days_kql_2026/blob/main/Datasets) (thank you Tom!).
