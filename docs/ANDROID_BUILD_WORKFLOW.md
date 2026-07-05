# Android Local Build Workflow

Use two separate paths. Device QA optimizes iteration speed; release packaging
optimizes distribution coverage. A successful APK build does not replace the
quality gate.

## Native project and version sources of truth

This repository uses Expo Continuous Native Generation:

- `app.json`, Expo plugins, package dependencies, and `eas.json` are source;
- `android/` is ignored, local generated output;
- a clean checkout may omit `android/`; the local build script runs
  `expo prebuild --platform android --no-install` automatically when needed;
- ordinary TypeScript/UI changes reuse the existing generated project;
- after changing native dependencies, Expo plugins, package identifiers, or
  native app configuration, run:

```powershell
npm run build:android:qa:prebuild
```

That command explicitly regenerates `android/` with Expo `--clean`. Never edit
ignored native files as the only copy of a product change.

`package.json` is the authoritative marketing version. `package-lock.json` and
`app.json > expo.version` must match it; `npm run check:version` enforces the
contract. Android `versionCode` and iOS `buildNumber` remain platform build
identifiers and increase independently.

## 1. Run the QA gate once per source-change batch

```powershell
npm run verify:android:qa
```

This runs route checks, TypeScript, and lint. The 8 GB value is only a process
ceiling; the generated display contract is emitted as bounded modules under
`constants/ev1DisplayContractsChunks/`, so TypeScript no longer parses one
18 MB source file. An OOM is a failed/unrun typecheck, never a pass.

The gate writes stable evidence to:

- `artifacts/android-qa-gate.log`;
- `artifacts/android-qa-gate.json`.

Feature-specific tests still run when their behavior changes. For the current
golden path, run the focused textbook/PageViewer tests named by the active
object and acceptance checklist.

## 2. Build the fast standalone QA APK

```powershell
npm run build:android:qa
```

The QA build:

- produces a standalone release-mode JS bundle;
- runs Expo bundling in non-interactive CI mode so repeated builds preserve the
  Metro cache instead of honoring React Native's unconditional `--reset-cache`;
- compiles only `arm64-v8a`, matching current physical Android devices;
- disables minification and resource shrinking;
- uses the Gradle build cache;
- uses a single-use Gradle process so roughly 2 GB is not left resident between
  builds on the constrained Windows workstation;
- runs Kotlin compilation in-process, avoiding sandbox-restricted daemon
  marker files;
- writes `artifacts/medlearn-qa-arm64.apk`.

The terminal shows a compact stage progress display instead of hundreds of
Gradle task lines:

```text
[  5%] Validate environment
[ 12%] Configure Gradle and Expo modules
[ 24%] Generate native bindings
[ 40%] Bundle JavaScript and assets
[ 60%] Compile arm64 native modules
[ 72%] Compile Kotlin and Java
[ 84%] Merge Android resources
[ 94%] Package and sign APK
[ 98%] Finalize APK
[100%] Complete
```

Percentages represent build phases, not Gradle's exact task count. The complete
raw output is saved to `artifacts/android-qa-build.log`. On failure, the script
automatically prints the final 80 log lines. Add `-ShowGradleOutput` when
running the PowerShell script directly to stream every Gradle line.

It intentionally does not rerun lint or typecheck. After a packaging failure,
fix the packaging issue and rerun this command without repeating the gate.

To run the gate and build together:

```powershell
npm run build:android:qa:verified
```

Use a clean build only when native dependencies or generated Android files
changed:

```powershell
npm run build:android:qa:clean
```

`build:android:qa:clean` cleans Gradle outputs but does not regenerate the
native project. Use `build:android:qa:prebuild` for native configuration
changes. Do not use either path for ordinary TypeScript, styling, copy, or
bundled-data changes.

## 3. Build a full local release APK only when required

```powershell
npm run build:android:local-release:verified
```

This keeps the Android project's full release ABI defaults and writes
`artifacts/medlearn-release-all-abi.apk`. Use it for final distribution
diagnostics, not every visual iteration. The verified command runs the complete
repository check before packaging; the packaging-only
`npm run build:android:local-release` command exists for retrying a failed
Gradle/package step after that gate has already passed.

Cloud preview and production commands remain:

```powershell
npm run build:android:preview
npm run build:android
```

## Expected cadence

```text
source batch
  -> verify:android:qa once
  -> build:android:qa
  -> install / inspect
  -> packaging-only retry: build:android:qa again
  -> final milestone only: full release build
```

The build script reports the output path, byte size, SHA-256, and elapsed time.
It also writes `android-qa-build.json` or `android-release-build.json` with the
source commit, dirty-worktree flag, ABI, hash, size, timestamp, and duration.
APK files stay under the git-ignored `artifacts/` directory.

## Artifact retention

Build outputs use stable names and overwrite their previous versions. Do not
create timestamped APK copies in `artifacts/`.

```powershell
# Read-only preview
npm run clean:android:artifacts

# Remove historical root-level APKs after reviewing the preview
npm run clean:android:artifacts:apply
```

The cleanup command keeps the current QA/release APKs and does not touch
screenshots, reports, `android/app/build`, or Gradle caches. Native caches are
performance infrastructure; remove them only when diagnosing a confirmed
native-build corruption.

On the current Windows workstation, the measured QA timings were:

- first successful arm64 QA build after cache changes: about 109 seconds;
- immediate repeat build: about 70 seconds;
- QA gate (route check + typecheck + lint): about 27 seconds.

The previous 14-minute attempt included two failed builds and a full multi-ABI
native compile; it is not the expected steady-state iteration time.
