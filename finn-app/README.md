# FINN frontend

Next.js app with a mobile portfolio digest and primary-source research view.

See [the root README](../README.md) for setup, data refresh, research configuration, testing, deployment and known limitations.

```sh
npm ci
npm run dev
npm run lint
npm run build
npm start
```

New ticker research requires a persistent Node/Python host and `FINN_ENABLE_RESEARCH=1`. Saved research is available without that flag.
