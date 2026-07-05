import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const packageJson = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'),
);
const buildScript = fs.readFileSync(
  path.join(ROOT, 'scripts', 'build-android-local.ps1'),
  'utf8',
);
const workflow = fs.readFileSync(
  path.join(ROOT, 'docs', 'ANDROID_BUILD_WORKFLOW.md'),
  'utf8',
);
const cleanupScript = fs.readFileSync(
  path.join(ROOT, 'scripts', 'clean-android-artifacts.ps1'),
  'utf8',
);
const gateScript = fs.readFileSync(
  path.join(ROOT, 'scripts', 'verify-android-qa.ps1'),
  'utf8',
);
const artifactReadme = fs.readFileSync(
  path.join(ROOT, 'artifacts', 'README.md'),
  'utf8',
);

test('typecheck uses the large generated-contract heap allowance', () => {
  assert.match(
    packageJson.scripts.typecheck,
    /--max-old-space-size=8192/,
  );
});

test('QA and release builds have separate commands', () => {
  assert.match(
    packageJson.scripts['build:android:qa'],
    /build-android-local\.ps1 -Mode qa/,
  );
  assert.match(
    packageJson.scripts['build:android:local-release'],
    /build-android-local\.ps1 -Mode release/,
  );
  assert.match(
    packageJson.scripts['build:android:local-release:verified'],
    /npm run check.*build:android:local-release/,
  );
  assert.match(
    packageJson.scripts['build:android:qa:verified'],
    /verify:android:qa.*build:android:qa/,
  );
});

test('fast QA build pins one ABI and avoids expensive release shrinking', () => {
  assert.match(buildScript, /reactNativeArchitectures=arm64-v8a/);
  assert.match(buildScript, /enableMinifyInReleaseBuilds=false/);
  assert.match(buildScript, /enableShrinkResourcesInReleaseBuilds=false/);
  assert.match(buildScript, /kotlin\.compiler\.execution\.strategy=in-process/);
  assert.match(buildScript, /--no-daemon/);
  assert.match(buildScript, /--build-cache/);
});

test('ignored Android native output is reproducible from Expo config', () => {
  assert.match(buildScript, /expo", "prebuild", "--platform", "android", "--no-install"/);
  assert.match(buildScript, /not \(Test-Path -LiteralPath \$gradleWrapper\)/);
  assert.match(buildScript, /if \(\$RegenerateNative\)/);
  assert.match(buildScript, /prebuildArgs \+= "--clean"/);
  assert.match(
    packageJson.scripts['build:android:qa:prebuild'],
    /build-android-local\.ps1 -Mode qa -RegenerateNative/,
  );
});

test('workflow separates verification from repeat packaging', () => {
  assert.match(workflow, /gate once per source-change batch/i);
  assert.match(workflow, /does not rerun lint or typecheck/i);
  assert.match(workflow, /Do not use either path for ordinary TypeScript/i);
});

test('build reports phase progress and preserves the complete Gradle log', () => {
  assert.match(buildScript, /Show-BuildPhase 40 "Bundle JavaScript and assets"/);
  assert.match(buildScript, /Show-BuildPhase 94 "Package and sign APK"/);
  assert.match(buildScript, /android-\$Mode-build\.log/);
  assert.match(buildScript, /Last 80 log lines/);
  assert.match(workflow, /Percentages represent build phases/i);
});

test('repeat packaging preserves the Metro cache', () => {
  assert.match(buildScript, /\$env:CI = "1"/);
  assert.match(workflow, /preserve the\s+Metro cache/);
});

test('gate and build emit stable machine-readable metadata', () => {
  assert.match(gateScript, /android-qa-gate\.json/);
  assert.match(gateScript, /dirtyFileCount/);
  assert.match(buildScript, /android-\$Mode-build\.json/);
  assert.match(buildScript, /sha256 = \$sha256/);
});

test('artifact cleanup is preview-first and restricted to historical APKs', () => {
  assert.match(
    packageJson.scripts['clean:android:artifacts'],
    /clean-android-artifacts\.ps1$/,
  );
  assert.match(
    packageJson.scripts['clean:android:artifacts:apply'],
    /clean-android-artifacts\.ps1 -Apply$/,
  );
  assert.match(cleanupScript, /Get-ChildItem .* -Filter "\*\.apk"/);
  assert.match(cleanupScript, /Remove-Item -LiteralPath/);
  assert.match(cleanupScript, /Preview only/);
  assert.match(artifactReadme, /Only two root-level APK names are retained/);
});
