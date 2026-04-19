# Jupyter (Containerized)

Do not run the notebooks directly on your host machine. The notebooks in this repository are intended to be run inside the provided Docker container so they use the correct Python environment, kernels, and dependencies.

How to use
- Start the project containers from the repository root (see `docker-compose.yml`):

```bash
docker compose up -d
```

- Open Jupyter using the URL printed by the container (typically http://127.0.0.1:8888). Do not run `jupyter lab` or `jupyter notebook` locally — run them inside the container.

Notes
- Files are mounted from the repository into the container, so any edits you make in the repo will be available inside the running container.
- Running notebooks locally may lead to missing packages or different kernel behavior; use the container for reproducible results.

If you need help starting the container, see the project README at the repository root.
