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
