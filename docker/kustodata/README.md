# kustodata

This directory is bind-mounted into the `kusto` container at `/kustodata` via the repository `docker-compose.yml`. It acts as the local persistent data area for the Kustainer emulator.

## Purpose

- Keep emulator data on the host machine instead of inside the container filesystem.
- Make it easier to inspect or clean up local state during development.
- Preserve data across container restarts as long as this directory is left in place.

## How It Is Wired

The `kusto` service mounts this directory with the `kustodata` volume:

```yaml
services:
	kusto:
		volumes:
			- kustodata:/kustodata
```

The named volume is configured as a bind mount back to this folder on the host.

## Notes

- Treat this as runtime state for the local emulator.
- Files here may be regenerated or changed by the container.
- If you want a completely clean local Kustainer state, stop the stack and remove the contents of this directory deliberately.

## Related Files

- `docker-compose.yml`
- `README.md`
