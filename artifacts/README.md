# Local Generated Artifacts

`artifacts/` contains reproducible local outputs and is not an authoritative
product or medical-content source. Everything except this README is ignored by
Git.

## Android retention contract

Only two root-level APK names are retained:

- `medlearn-qa-arm64.apk` — current physical-device QA package;
- `medlearn-release-all-abi.apk` — current full local release package.

Each successful build overwrites its stable APK, log, and JSON metadata:

- `android-qa-build.log` / `android-qa-build.json`;
- `android-release-build.log` / `android-release-build.json`;
- `android-qa-gate.log` / `android-qa-gate.json`.

Historical root-level APKs are not retained. Preview cleanup with:

```powershell
npm run clean:android:artifacts
```

Apply the reviewed cleanup with:

```powershell
npm run clean:android:artifacts:apply
```

The cleanup script is deliberately restricted to root-level `.apk` files under
this directory and never removes screenshots, audit notes, reports, Gradle
caches, or native build intermediates.

## Other directories

- `qa/` and dated audit folders: screenshots and manual acceptance evidence;
- `analysis/`, `benchmarks/`, `pilot-reports/`: reproducible reports;
- `pipeline-output/`, `legacy-ingestion/`: non-authoritative pipeline output.

Do not store credentials, service-role keys, protected answers, scoring
rubrics, reviewer fields, or patient data here.
