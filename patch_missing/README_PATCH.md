# Retry missing pbpstats.com AdjTS rows

This patch changes the builder to use per-player pbpstats.com API requests instead of trusting the all-player endpoint. It also adds:

```bash
--missing-only
```

Use it to retry only player-game rows that are still not verified.
