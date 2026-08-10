import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { extensionRoot, readJson, walkFiles } from "./support.mjs";

const manifestUrl = new URL("manifest.json", extensionRoot);

function extensionFile(relativePath) {
  assert.equal(typeof relativePath, "string");
  assert(relativePath.length > 0, "manifest path must not be empty");
  const url = new URL(relativePath, extensionRoot);
  assert(
    url.href.startsWith(extensionRoot.href),
    `manifest path escapes the extension root: ${relativePath}`,
  );
  return url;
}

async function assertRegularFile(url) {
  assert((await stat(url)).isFile(), `${fileURLToPath(url)} must be a file`);
}

function openingTags(html, name) {
  return [...html.matchAll(new RegExp(`<${name}\\b[^>]*>`, "gi"))].map(
    (match) => match[0],
  );
}

function hasAttribute(tag, name, value) {
  const quotedValue = value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(
    `\\b${name}\\s*=\\s*(["'])${quotedValue}\\1`,
    "i",
  ).test(tag);
}

test("manifest is a loadable MV3 shell with module service worker and popup", async () => {
  const manifest = await readJson(manifestUrl);

  assert.equal(manifest.manifest_version, 3);
  assert.equal(manifest.name, "GPT Live Voice Converter");
  assert.equal(manifest.version, "0.4.0");
  assert.equal(manifest.action?.default_title, "GPT Live Voice Converter · v0.4.0");

  assert.equal(manifest.background?.type, "module");
  assert(Number.parseInt(manifest.minimum_chrome_version, 10) >= 116);
  assert.deepEqual(new Set(manifest.permissions), new Set([
    "activeTab",
    "offscreen",
    "storage",
    "tabCapture",
  ]));
  await assertRegularFile(extensionFile(manifest.background?.service_worker));
  await assertRegularFile(extensionFile(manifest.action?.default_popup));
  await assertRegularFile(extensionFile("offscreen/offscreen.html"));
  await assertRegularFile(extensionFile("offscreen/offscreen.js"));
  await assertRegularFile(
    extensionFile("offscreen/worklets/liveconv-audio.js"),
  );

  const syntax = spawnSync(
    process.execPath,
    ["--check", fileURLToPath(extensionFile(manifest.background.service_worker))],
    { encoding: "utf8" },
  );
  assert.equal(syntax.status, 0, syntax.stderr || syntax.stdout);
});

test("popup exposes session and generation lifecycle controls and visible state", async () => {
  const manifest = await readJson(manifestUrl);
  const popupUrl = extensionFile(manifest.action?.default_popup);
  const html = await readFile(popupUrl, "utf8");
  const buttons = openingTags(html, "button");

  for (const action of [
    "start",
    "stop",
    "end",
    "cancel",
    "next",
    "models",
  ]) {
    const button = buttons.find((tag) => hasAttribute(tag, "data-action", action));
    assert(button, `popup must expose a ${action} button`);
    assert.match(button, /\baria-label\s*=\s*(["']).+?\1/i);
  }
  const configure = buttons.find((tag) =>
    hasAttribute(tag, "data-action", "configure"),
  );
  assert(configure, "popup must expose a configure button");
  assert.match(
    configure,
    /\bdisabled\b/i,
    "configuration must stay disabled until initial status synchronization",
  );
  const token = openingTags(html, "input").find((tag) =>
    hasAttribute(tag, "name", "token"),
  );
  assert(token && /\brequired\b/i.test(token));
  const profile = openingTags(html, "select").find((tag) =>
    hasAttribute(tag, "name", "profileId"),
  );
  assert(profile, "popup must expose one model selector");
  assert(/\brequired\b/i.test(profile));

  assert.match(
    html,
    /data-role=(['"])build-version\1[^>]*>Realtime Voice · v0\.4\.0</i,
    "popup must visibly identify the loaded UI build",
  );

  const status = openingTags(html, "output").find((tag) =>
    hasAttribute(tag, "data-role", "session-status"),
  );
  assert(status, "popup must expose a session status output");
  assert.match(status, /\baria-live\s*=\s*(["'])(polite|assertive)\1/i);

  assert.doesNotMatch(html, /<script\b(?![^>]*\bsrc\s*=)[^>]*>/i);
  const scripts = openingTags(html, "script");
  assert(scripts.length > 0, "popup must load an external script");
  for (const script of scripts) {
    const source = script.match(/\bsrc\s*=\s*(["'])([^"']+)\1/i)?.[2];
    assert(source, "popup scripts must use src");
    await assertRegularFile(new URL(source, popupUrl));
  }
});

test("manifest requests no broad host or secret-bearing browser permissions", async () => {
  const manifest = await readJson(manifestUrl);
  assert.deepEqual(manifest.host_permissions, undefined);
  assert.deepEqual(new Set(manifest.optional_host_permissions), new Set([
    "http://127.0.0.1/*",
    "http://localhost/*",
    "https://*/*",
  ]));
  const forbiddenPermissions = new Set([
    "cookies",
    "debugger",
    "history",
    "identity",
    "identity.email",
    "management",
    "nativeMessaging",
    "privacy",
    "proxy",
    "webRequest",
    "webRequestBlocking",
  ]);
  for (const permission of manifest.permissions ?? []) {
    assert(
      !forbiddenPermissions.has(permission),
      `unnecessary sensitive permission: ${permission}`,
    );
  }

  const broadOrigins = new Set([
    "<all_urls>",
    "*://*/*",
    "http://*/*",
    "https://*/*",
  ]);
  for (const origin of manifest.host_permissions ?? []) {
    assert(!broadOrigins.has(origin), `broad host permission: ${origin}`);
  }
  for (const match of manifest.content_scripts?.flatMap((entry) => entry.matches) ?? []) {
    assert(!broadOrigins.has(match), `broad content-script match: ${match}`);
  }

  const extensionPolicy = manifest.content_security_policy?.extension_pages ?? "";
  assert.doesNotMatch(extensionPolicy, /unsafe-eval/i);
  assert.doesNotMatch(extensionPolicy, /\bhttp:/i);
});

test("extension bundle contains no embedded credentials", async () => {
  const secretPatterns = [
    /-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----/,
    /\bAKIA[0-9A-Z]{16}\b/,
    /\bgh[pousr]_[A-Za-z0-9_]{20,}\b/,
    /\bsk-[A-Za-z0-9]{20,}\b/,
    /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/,
    /\bAuthorization\s*[:=]\s*(["'])Bearer\s+[^"']+\1/i,
  ];
  const files = await walkFiles(extensionRoot, {
    exclude: new Set(["node_modules", "tests"]),
  });

  for (const file of files) {
    const content = await readFile(file);
    if (content.includes(0)) {
      continue;
    }
    const text = content.toString("utf8");
    for (const pattern of secretPatterns) {
      assert.doesNotMatch(text, pattern, `credential-like content in ${file.href}`);
    }
  }
});
