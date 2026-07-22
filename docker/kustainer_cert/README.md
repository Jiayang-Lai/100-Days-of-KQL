# kustainer_cert

This directory is bind-mounted into the `kusto` container at `/kustainer_cert` via the repository `docker-compose.yml`. It stores the local certificate material used to help Kustainer trust the repo's Caddy HTTPS endpoint.

## Purpose

- Hold the local Caddy root certificate copied from the `caddy` container.
- Provide a stable host-side location that can be mounted into the `kusto` container.
- Support the `make trust` workflow for enabling TLS access from Kustainer to locally served sample files.

## Trust Workflow

Running `make trust` performs two steps defined in `Makefile`:

1. Copy Caddy's generated local root CA certificate into this directory as `root.ignore.crt`.
2. Append that certificate to the Kustainer container's CA bundle.

Current command flow:

```make
trust:
	docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./docker/kustainer_cert/root.ignore.crt
	docker exec kusto sh -c "cat /kustainer_cert/root.ignore.crt >> /etc/ssl/certs/ca-certificates.crt"
```

## Notes

- `root.ignore.crt` is generated local development material and should not be treated as a production certificate.
- Re-run `make trust` if the Caddy certificate is regenerated or if the Kustainer container is recreated.
- This directory exists to support secure local `https://` access to files served by Caddy.

## Related Files

- `Makefile`
- `docker-compose.yml`
- `README.md`
