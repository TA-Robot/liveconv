import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  createAppFlow,
  createSourceCaptureUploadFlow,
  evaluationCopyText,
  evaluationScriptBlocks,
  defaultCollectionId,
  isReviewableNote,
} from "../app.js";
import {
  GROSS_REVIEW_STORE_KEY,
  JUDGMENT_STORE_KEY,
  LIBRARY_STORE_KEY,
  MAX_GROSS_REVIEW_REASON_LENGTH,
  PlaybackController,
  candidatesForCollection,
  candidatesFromIndex,
  candidatesFromLibrary,
  comparisonCandidates,
  grossReviewDocument,
  grossReviewKey,
  judgmentDocument,
  nextPlayableIndex,
  normalizeGrossReview,
  normalizeJudgment,
  normalizedLoop,
  readGrossReviewStorage,
  readJudgmentStorage,
  pronunciationReviewCandidates,
  pronunciationReviewDocument,
  SOURCE_PRONUNCIATION_EVIDENCE_SCHEMA,
  SOURCE_PRONUNCIATION_REVIEW_SCOPE,
  toggleGrossReview,
} from "../core.js";

class FakeAudio {
  constructor() { this.currentTime = 0; this.duration = 8; this.volume = 1; this.paused = true; this.listeners = new Map(); }
  addEventListener(type, listener) { this.listeners.set(type, listener); }
  play() { this.paused = false; return Promise.resolve(); }
  pause() { this.paused = true; }
  tick(time) { this.currentTime = time; this.listeners.get("timeupdate")?.(); }
}

class AppFlowAudio {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, listener) { this.listeners.set(type, listener); }
  fire(type) { this.listeners.get(type)?.(); }
}

test("candidate parser keeps source and only passed variants", () => {
  const candidates = candidatesFromIndex({ source_file: "source.wav", variants: [{ status: "failed", output_file: "bad.wav" }, { status: "passed", variant_id: "good", output_file: "good.wav", display_order: 1 }] });
  assert.deepEqual(candidates.map((item) => item.id), ["source", "good"]);
  assert.equal(normalizedLoop({ start: 1, end: 2 }, 8).end, 2);
  assert.equal(normalizedLoop({ start: 2, end: 2 }, 8), null);
});

test("A/B switch and seeks preserve the same playback position", () => {
  const audios = [];
  const controller = new PlaybackController({ audioFactory: () => { const audio = new FakeAudio(); audios.push(audio); return audio; } });
  const candidate = (name) => ({ outputFile: `${name}.wav`, absolutePeak: 0.2 });
  controller.load("a", candidate("a"), 0.8, false); controller.load("b", candidate("b"), 0.8, false); controller.seek(3.25); controller.toggle(); controller.select("b");
  assert.equal(audios[0].currentTime, 3.25); assert.equal(audios[1].currentTime, 3.25); assert.equal(audios[0].paused, true); assert.equal(audios[1].paused, false);
  controller.setLoop({ start: 1, end: 2 }); audios[1].tick(2.1); assert.equal(audios[1].currentTime, 1);
});

test("library candidates retain collection context and sequence wraps", () => {
  const library = { collections: [{ id: "queue", title: "EXP-019" }], runs: [{ id: "run-1", title: "Run one", collection_id: "queue", candidates: [{ id: "source", kind: "source", audio_url: "/source.wav" }, { id: "voice", kind: "candidate", audio_url: "/voice.wav" }] }] };
  const candidates = candidatesFromLibrary(library);
  assert.deepEqual(candidatesForCollection(candidates, "queue").map((item) => item.id), ["source", "voice"]);
  assert.equal(nextPlayableIndex(candidates, 1, 1), 0);
  assert.equal(nextPlayableIndex(candidates, 0, -1), 1);
});

test("judgment states are mutually exclusive and winner needs an eligible candidate", () => {
  assert.deepEqual(
    normalizeJudgment({ state: "winner", winner_candidate_id: "missing", defect_tags: ["naturalness", "bad"], note: " x " }, ["voice-a"]),
    { state: "unheard", winner_candidate_id: null, defect_tags: ["naturalness"], note: "x" },
  );
  assert.deepEqual(
    normalizeJudgment({ state: "tie", winner_candidate_id: "voice-a" }, ["voice-a"]),
    { state: "tie", winner_candidate_id: null, defect_tags: [], note: "" },
  );
});

test("legacy checkbox selection migration never infers a winner", () => {
  const comparisons = { r1: ["voice-a", "voice-b"], r2: ["voice-c"] };
  const migrated = readJudgmentStorage(null, JSON.stringify(["voice-a"]), comparisons);
  assert.equal(migrated.migrated, true);
  assert.deepEqual(migrated.judgments, {
    r1: { state: "unheard", winner_candidate_id: null, defect_tags: [], note: "" },
    r2: { state: "unheard", winner_candidate_id: null, defect_tags: [], note: "" },
  });
  assert.equal(readJudgmentStorage("{", "{", comparisons).judgments.r1.state, "unheard");
});

test("judgment export persists one comparison record with the winning receipt", () => {
  const library = {
    generated_at: "2026-08-11T00:00:00Z",
    collections: [{ id: "queue", title: "EXP-019" }],
    runs: [{ id: "r1", title: "Run", collection_id: "queue", candidates: [] }],
  };
  const candidates = [
    { id: "source", kind: "source", display_name: "Source", runId: "r1" },
    { id: "voice-a", kind: "candidate", display_name: "Voice A", runId: "r1", runTitle: "Run", profile_id: "vc.rvc.a", family_id: "rvc", output_file: "voice-a.wav" },
    { id: "voice-b", kind: "candidate", display_name: "Voice B", runId: "r1", runTitle: "Run", profile_id: "vc.rvc.b", family_id: "rvc", output_file: "voice-b.wav", route_status: "route_qualified" },
  ];
  library.runs[0].candidates = candidates;
  assert.deepEqual(comparisonCandidates(library, candidates), { r1: ["voice-a", "voice-b"] });
  const exported = judgmentDocument(library, candidates, {
    r1: { state: "winner", winner_candidate_id: "voice-b", defect_tags: ["naturalness"], note: "少し硬い" },
  });
  assert.equal(exported.schema_version, 2);
  assert.deepEqual(exported.judgment_counts, { winner: 1, tie: 0, both_bad: 0, unheard: 0 });
  assert.equal(exported.comparisons[0].winner.profile_id, "vc.rvc.b");
  assert.equal(exported.comparisons[0].winner.route_status, "route_qualified");
  assert.deepEqual(exported.comparisons[0].defect_tags, ["naturalness"]);
});

test("gross review actions default, toggle, persist, isolate collections, and export separately", () => {
  const library = {
    generated_at: "2026-08-12T11:45:00Z",
    collections: [
      { id: "exp020", title: "EXP-020" },
      { id: "exp021", title: "EXP-021" },
    ],
    runs: [
      { id: "run-020", title: "EXP-020 render", collection_id: "exp020" },
      { id: "run-021", title: "EXP-021 render", collection_id: "exp021" },
    ],
  };
  const source = { id: "source", kind: "source", collectionId: "exp021", runId: "run-021" };
  const exp020 = { id: "same-variant", kind: "candidate", collectionId: "exp020", collectionTitle: "EXP-020", runId: "run-020", runTitle: "EXP-020 render", display_name: "MeanVC2 EXP-020", profile_id: "vc.meanvc2", family_id: "meanvc2", output_file: "mean-020.wav" };
  const exp021 = { id: "same-variant", kind: "candidate", collectionId: "exp021", collectionTitle: "EXP-021", runId: "run-021", runTitle: "EXP-021 render", display_name: "OpenVoice V2 EXP-021", profile_id: "vc.openvoice-v2", family_id: "openvoice-v2", output_file: "open-021.wav", output_sha256: "sha256:output" };
  const candidates = [source, exp020, exp021];
  const initial = readGrossReviewStorage(null, candidates);
  assert.deepEqual(initial.reviews[grossReviewKey(exp020)], { action: "unreviewed", reason: "" });
  assert.deepEqual(initial.reviews[grossReviewKey(exp021)], { action: "unreviewed", reason: "" });
  assert.equal(grossReviewKey(source), null);

  const exp021Continue = { ...toggleGrossReview(initial.reviews[grossReviewKey(exp021)], "continue"), reason: "高域が割れる" };
  assert.deepEqual(exp021Continue, { action: "continue", reason: "高域が割れる" });
  assert.deepEqual(toggleGrossReview(exp021Continue, "continue"), { action: "unreviewed", reason: "高域が割れる" });
  const reviews = { ...initial.reviews, [grossReviewKey(exp021)]: exp021Continue };
  const persisted = JSON.stringify({ schema_version: 1, reviews });
  const reloaded = readGrossReviewStorage(persisted, candidates);
  assert.equal(reloaded.migrated, true);
  assert.deepEqual(reloaded.reviews[grossReviewKey(exp021)], { action: "continue", reason: "高域が割れる" });
  assert.deepEqual(reloaded.reviews[grossReviewKey(exp020)], { action: "unreviewed", reason: "" });

  const exported = grossReviewDocument(library, candidates, reloaded.reviews);
  assert.equal(exported.schema_version, 2);
  assert.equal(exported.document_type, "liveconv-ms3-gross-review-actions");
  assert.equal(exported.gross_review_count, 2);
  assert.deepEqual(exported.action_counts, { continue: 1, rejected: 0, unreviewed: 1 });
  assert.deepEqual(exported.gross_review_actions.map((entry) => [entry.collection_label, entry.run_label, entry.candidate_label, entry.action, entry.reason]), [
    ["EXP-020", "EXP-020 render", "MeanVC2 EXP-020", "unreviewed", null],
    ["EXP-021", "EXP-021 render", "OpenVoice V2 EXP-021", "continue", "高域が割れる"],
  ]);
  assert.doesNotMatch(JSON.stringify(exported), /winner|pass|rank/i);

  const ordinary = judgmentDocument(
    { generated_at: library.generated_at, runs: [{ id: "ordinary", title: "ordinary", collection_id: "ordinary" }] },
    [{ id: "ordinary:candidate", kind: "candidate", runId: "ordinary", display_name: "ordinary" }],
    { ordinary: { state: "unheard" } },
  );
  assert.equal("gross_review_actions" in ordinary, false);
  assert.deepEqual(Object.keys(ordinary).sort(), ["comparison_count", "comparisons", "exported_at", "judgment_counts", "library_generated_at", "schema_version"]);
});

test("gross review normalizes short reasons and keeps them across action toggles", () => {
  assert.deepEqual(
    normalizeGrossReview({ action: "rejected", reason: "  子音が崩れる  " }),
    { action: "rejected", reason: "子音が崩れる" },
  );
  assert.deepEqual(
    normalizeGrossReview({ action: "unknown", reason: `  ${"x".repeat(MAX_GROSS_REVIEW_REASON_LENGTH + 1)}  ` }),
    { action: "unreviewed", reason: "x".repeat(MAX_GROSS_REVIEW_REASON_LENGTH) },
  );
  assert.deepEqual(
    toggleGrossReview({ action: "rejected", reason: "音割れ" }, "rejected"),
    { action: "unreviewed", reason: "音割れ" },
  );
  assert.deepEqual(
    toggleGrossReview({ action: "rejected", reason: "音割れ" }, "continue"),
    { action: "continue", reason: "音割れ" },
  );
});

test("scoped heldout source pronunciation review is fail-closed and exports its bindings", async () => {
  const bindings = {
    candidate_lock_sha256: "sha256:candidate-lock",
    review_bundle_sha256: "sha256:review-bundle",
    review_scope: SOURCE_PRONUNCIATION_REVIEW_SCOPE,
    source_only: true,
    evidence_schema: SOURCE_PRONUNCIATION_EVIDENCE_SCHEMA,
  };
  const ordinaryTrain = { id: "train", audio_url: "/train.wav", split: "train" };
  const ordinaryHeldout = { id: "heldout", audio_url: "/heldout.wav", split: "heldout" };
  const missingEvidenceSchema = {
    id: "missing-evidence", audio_url: "/missing-evidence.wav", split: "heldout", ...bindings,
  };
  delete missingEvidenceSchema.evidence_schema;
  const scopedHeldout = {
    id: "scoped-heldout",
    audio_url: "/scoped-heldout.wav",
    split: "heldout",
    ...bindings,
    target_wav: "must-not-export.wav",
    target_model: "must-not-export",
  };

  const eligible = pronunciationReviewCandidates([
    ordinaryTrain,
    ordinaryHeldout,
    missingEvidenceSchema,
    scopedHeldout,
  ]);
  assert.deepEqual(eligible.map((record) => record.id), ["train", "scoped-heldout"]);

  const exported = pronunciationReviewDocument(bindings, eligible, {
    [JSON.stringify([null, null, "scoped-heldout", "scoped-heldout", null])]: {
      action: "exclude",
      reason: "発音確認",
    },
  });
  assert.equal(exported.review_count, 2);
  assert.deepEqual(
    Object.fromEntries(Object.keys(bindings).map((field) => [field, exported.reviews[1][field]])),
    bindings,
  );
  assert.deepEqual(
    Object.fromEntries(Object.keys(bindings).map((field) => [field, exported[field]])),
    bindings,
  );
  assert.equal("candidate_lock_sha256" in exported.reviews[0], false);
  assert.doesNotMatch(JSON.stringify(exported), /target_wav|target_model/);

  const appSource = await readFile(new URL("../app.js", import.meta.url), "utf8");
  assert.match(appSource, /candidate\.source_only === true\s*\? "SOURCE"/);
});

test("schema-v1 gross review storage migrates actions with empty reasons", () => {
  const candidate = { id: "candidate", kind: "candidate", collectionId: "exp023", runId: "run-023" };
  const key = grossReviewKey(candidate);
  const migrated = readGrossReviewStorage(JSON.stringify({
    schema_version: 1,
    reviews: { [key]: { action: "rejected" } },
  }), [candidate]);

  assert.equal(migrated.migrated, true);
  assert.deepEqual(migrated.reviews[key], { action: "rejected", reason: "" });
});

test("curated collection annotations expose experiment settings and checkpoints", async () => {
  const notes = JSON.parse(await readFile(new URL("../collection-notes.json", import.meta.url), "utf8"));
  assert.equal(notes.schema_version, 1);
  assert.match(notes.top_status.updated_at, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
  for (const annotation of notes.collections) {
    assert.equal(typeof annotation.display_title, "string");
    assert.ok(annotation.display_title.length > 0);
    assert.equal(typeof annotation.data, "string");
  }
  const exp010 = notes.collections.find((annotation) => annotation.match_all.join("|") === "exp010");
  const exp020 = notes.collections.find((annotation) => annotation.match_all.join("|") === "exp020-human-rvc-smoke-8s-plain");
  const exp021 = notes.collections.find((annotation) => annotation.match_all.join("|") === "exp021-zero-shot-gross-8s-plain-20260812");
  const exp023 = notes.collections.find((annotation) => annotation.match_all.join("|") === "exp023-qwen3-tts-ono-anna-ja12-plain");
  const exp025ListenNow = notes.collections.find((annotation) => annotation.match_all.join("|") === "exp025-whole-short-87-listen-now");
  const exp025 = notes.collections.find((annotation) => annotation.match_all.join("|") === "exp025-hadou-source-pronunciation-review");
  const exp015 = notes.collections.find((annotation) => annotation.match_all.join("|") === "exp015-xvc-target-conditioning-render-v1");
  const exp019 = notes.collections.find((annotation) => annotation.match_all.join("|") === "exp019");
  assert.match(exp010.candidate_labels["Candidate A"], /LoRA r8.*update 192/);
  assert.match(exp015.candidate_labels["Candidate A"], /zeros/);
  assert.match(exp015.candidate_labels["Candidate B"], /synthetic_target/);
  assert.equal(Object.keys(exp019.candidate_labels_by_sha256).length, 8);
  assert.equal(exp020.review_mode, "gross_reject_only");
  assert.equal(isReviewableNote(exp020), false);
  assert.equal(exp021.display_title, "EXP-021: 実入力8.17秒・ゼロショットVCの粗い失敗確認");
  assert.match(exp021.purpose, /同じ実際の変換前VC 8\.17秒の早口言葉入力/);
  assert.match(exp021.purpose, /MeanVC2 Runrun Q007 ゼロショット/);
  assert.match(exp021.purpose, /OpenVoice V2 Runrun Q007 ゼロショット/);
  assert.match(exp021.data, /新規学習なし/);
  assert.match(exp021.status, /技術レンダーのみ・operator 未レビュー/);
  assert.match(exp021.status, /粗い却下だけ/);
  assert.match(exp021.status, /合格・勝者・リアルタイム・E2E の主張はしません/);
  assert.equal(exp020.review_priority, "highest");
  assert.equal(exp021.review_priority, "priority");
  assert.equal(exp021.review_mode, "gross_reject_only");
  assert.equal(isReviewableNote(exp021), false);
  assert.equal(exp021.candidate_labels, undefined);
  assert.equal(exp021.candidate_labels_by_sha256, undefined);
  assert.equal(exp023.display_title, "EXP-023: Qwen3-TTS 1.7B / Ono_Anna / 日本語12文");
  assert.match(exp023.purpose, /日本語テキストから直接音声を生成/);
  assert.match(exp023.data, /固定日本語12文/);
  assert.match(exp023.data, /新規学習なし/);
  assert.match(exp023.status, /operator未レビュー/);
  assert.equal(exp023.review_priority, "next");
  assert.equal(exp023.review_mode, "gross_reject_only");
  assert.match(exp025ListenNow.display_title, /whole-short 87ペア/);
  assert.match(exp025ListenNow.data, /heldout targetは未使用/);
  assert.match(exp025ListenNow.status, /adaptedが明確に良ければkeep/);
  assert.equal(exp025ListenNow.review_priority, "normal");
  assert.equal(exp025.review_mode, "pronunciation_keep_exclude");
  assert.match(exp025.data, /source-only/);
  assert.equal(isReviewableNote(exp023), false);
  assert.match(notes.top_status.current, /EXP-020/);
  assert.match(notes.top_status.current, /EXP-021/);
  assert.match(notes.top_status.current, /EXP-023/);
  assert.match(notes.top_status.next, /continue/);
  assert.match(notes.top_status.next, /rejected/);
  assert.equal(isReviewableNote(exp010), true);
  assert.doesNotMatch(JSON.stringify(notes), /blind|reblind/i);
});

test("gross review exposes only direct actions and excludes ordinary comparison export", async () => {
  const appSource = await readFile(new URL("../app.js", import.meta.url), "utf8");
  const htmlSource = await readFile(new URL("../index.html", import.meta.url), "utf8");
  assert.match(appSource, /review_mode !== "gross_reject_only"/);
  assert.match(appSource, /choice\.hidden = true/);
  assert.match(appSource, /候補ごとに、次の比較に残すか却下かだけを記録します。/);
  assert.match(appSource, /candidate\.kind === "source"/);
  assert.match(appSource, /grossReviewDocument/);
  assert.match(appSource, /if \(run\.source_file\) parts\.push\(run\.source_file\)/);
  assert.match(appSource, /if \(!reviewEnabled\(run\)\) delete state\.comparisons\[run\.id\]/);
  assert.match(htmlSource, /data-gross-review-action="continue"/);
  assert.match(htmlSource, /data-gross-review-action="rejected"/);
  assert.match(htmlSource, /class="gross-review-actions"[^>]*hidden/);
  assert.match(htmlSource, /<textarea[^>]*class="gross-review-reason"[^>]*maxlength="240"/);
  assert.match(htmlSource, /id="gross-review-count"/);
  assert.match(htmlSource, /id="export-gross-review"/);
});

test("listener opens the highest-priority EXP-020 collection instead of all history", async () => {
  const notes = JSON.parse(await readFile(new URL("../collection-notes.json", import.meta.url), "utf8"));
  const library = {
    runs: [],
    collections: [
      { id: "history", title: "exp010-xvc-checkpoint-demo" },
      { id: "former-current", title: "exp020-human-rvc-smoke-8s-plain-20260812" },
      { id: "exp021", title: "exp021-zero-shot-gross-8s-plain-20260812" },
      { id: "current", title: "exp023-qwen3-tts-ono-anna-ja12-plain-20260812" },
    ],
  };
  assert.equal(defaultCollectionId(library, notes), "former-current");
  assert.equal(defaultCollectionId(library, { collections: [] }), "all");
});

test("evaluation script keeps 100 entries in ten ordered copyable blocks", async () => {
  const script = JSON.parse(await readFile(
    new URL("../../../experiments/EXP-020-human-rvc-actual-input/source-evaluation-script.v1.json", import.meta.url),
    "utf8",
  ));
  const blocks = evaluationScriptBlocks(script);
  assert.equal(blocks.length, 10);
  assert.deepEqual(blocks.map((block) => block.length), Array(10).fill(10));
  assert.equal(blocks[0][0].id, "SRC001");
  assert.equal(blocks.at(-1).at(-1).id, "SRC100");
  const copied = evaluationCopyText(blocks[0]);
  assert.match(copied, /約1秒/);
  assert.match(copied, /余計な説明・番号・前置き/);
  assert.match(copied, new RegExp(blocks[0][0].text));
  assert.doesNotMatch(copied, /SRC001|short_response/);
  const appSource = await readFile(new URL("../app.js", import.meta.url), "utf8");
  const htmlSource = await readFile(new URL("../index.html", import.meta.url), "utf8");
  assert.match(appSource, /source-evaluation-script\.json/);
  assert.match(appSource, /renderEvaluationScript/);
  assert.match(appSource, /本文をコピー/);
  assert.match(htmlSource, /本評価の収録台本/);
  assert.match(htmlSource, /id="evaluation-script-blocks"/);
});

test("app flow wires playback, judgment persistence, and downloads through injected browser APIs", async () => {
  const audio = new AppFlowAudio();
  const entries = new Map([[LIBRARY_STORE_KEY, JSON.stringify(["voice-a"])]]);
  const storage = { getItem(key) { return entries.get(key) ?? null; }, setItem(key, value) { entries.set(key, value); } };
  let link;
  const document = { createElement(tag) { assert.equal(tag, "a"); link = { clicked: false, click() { this.clicked = true; } }; return link; } };
  const url = { created: [], revoked: [], createObjectURL(blob) { this.created.push(blob); return "blob:selection"; }, revokeObjectURL(value) { this.revoked.push(value); } };
  class FakeBlob { constructor(parts, options) { this.parts = parts; this.options = options; } }
  const playing = []; let activeRows = 0; let autoAdvance = true; let advances = 0;
  const flow = createAppFlow({ audio, storage, document, url, Blob: FakeBlob, isAutoAdvanceEnabled: () => autoAdvance, onPlayingChange: (value) => playing.push(value), onAdvance: () => { advances += 1; }, onActiveRow: () => { activeRows += 1; }, clock: () => new Date("2026-08-11T12:34:56.000Z") });

  const comparisons = { r1: ["voice-a", "voice-b"] };
  assert.equal(flow.readJudgments(comparisons).judgments.r1.state, "unheard");
  flow.saveJudgments({ r1: { state: "winner", winner_candidate_id: "voice-b", defect_tags: [], note: "" } });
  assert.equal(JSON.parse(entries.get(JUDGMENT_STORE_KEY)).judgments.r1.winner_candidate_id, "voice-b");
  entries.set(JUDGMENT_STORE_KEY, "{");
  assert.equal(flow.readJudgments(comparisons).judgments.r1.state, "unheard");

  flow.bindAudioEvents(); audio.fire("play"); audio.fire("pause"); audio.fire("ended"); autoAdvance = false; audio.fire("ended");
  assert.deepEqual(playing, [true, false, false, false]); assert.equal(advances, 1); assert.equal(activeRows, 3);

  const payload = { comparisons: ["r1"] }; const filename = flow.downloadJson(payload);
  assert.equal(filename, "ms3-listening-selection-2026-08-11T12-34-56.000Z.json"); assert.equal(link.href, "blob:selection"); assert.equal(link.download, filename); assert.equal(link.clicked, true); assert.deepEqual(url.revoked, ["blob:selection"]); assert.equal(url.created[0].options.type, "application/json");

  const appSource = await readFile(new URL("../app.js", import.meta.url), "utf8");
  assert.match(appSource, /appFlow\.readJudgments\(state\.comparisons\)/); assert.match(appSource, /appFlow\.saveJudgments\(state\.judgments\)/); assert.match(appSource, /renderCollectionTabs\(\)/);
  assert.match(appSource, /explicitCandidateLabel/); assert.match(appSource, /Object\.keys\(state\.comparisons\)/);
  assert.match(appSource, /textarea, select, \[contenteditable\]/);
  assert.match(appSource, /注釈を読み込めないため判定を停止/);
  const htmlSource = await readFile(new URL("../index.html", import.meta.url), "utf8"); const styleSource = await readFile(new URL("../style.css", import.meta.url), "utf8");
  assert.match(htmlSource, /id="library-search"/); assert.match(htmlSource, /data-judgment-state="tie"/); assert.match(styleSource, /overflow-x: auto/);
});

test("app flow persists gross review actions separately and names their export", () => {
  const audio = new AppFlowAudio();
  const entries = new Map();
  const storage = { getItem(key) { return entries.get(key) ?? null; }, setItem(key, value) { entries.set(key, value); } };
  let link;
  const document = { createElement() { link = { clicked: false, click() { this.clicked = true; } }; return link; } };
  const url = { createObjectURL() { return "blob:gross-review"; }, revokeObjectURL() {} };
  class FakeBlob { constructor(parts, options) { this.parts = parts; this.options = options; } }
  const flow = createAppFlow({ audio, storage, document, url, Blob: FakeBlob, isAutoAdvanceEnabled: () => false, onPlayingChange() {}, onAdvance() {}, onActiveRow() {}, clock: () => new Date("2026-08-12T12:34:56.000Z") });
  const candidate = { id: "candidate", kind: "candidate", collectionId: "exp021", runId: "run-021" };
  const reviews = { [grossReviewKey(candidate)]: { action: "rejected", reason: "子音が崩れる" } };

  flow.saveGrossReviews(reviews);
  const stored = JSON.parse(entries.get(GROSS_REVIEW_STORE_KEY));
  assert.equal(stored.schema_version, 2);
  assert.equal(stored.reviews[grossReviewKey(candidate)].action, "rejected");
  assert.equal(stored.reviews[grossReviewKey(candidate)].reason, "子音が崩れる");
  assert.deepEqual(flow.readGrossReviews([candidate]).reviews[grossReviewKey(candidate)], { action: "rejected", reason: "子音が崩れる" });

  const filename = flow.downloadJson({ document_type: "liveconv-ms3-gross-review-actions" }, "ms3-listening-gross-review-actions");
  assert.equal(filename, "ms3-listening-gross-review-actions-2026-08-12T12-34-56.000Z.json");
  assert.equal(link.download, filename);
  assert.equal(link.clicked, true);
});

test("source capture upload flow uses generated chunk names and reports server metadata", async () => {
  const uploads = [];
  const progress = [];
  const crypto = {
    subtle: webcrypto.subtle,
    getRandomValues(values) {
      values.set([0, 1, 2, 3, 4, 5, 6, 7]);
      return values;
    },
  };
  const flow = createSourceCaptureUploadFlow({
    cryptoImpl: crypto,
    clock: () => new Date("2026-08-12T12:00:00.000Z"),
    fetchImpl: async (target, init) => {
      uploads.push({ target, init });
      return {
        ok: true,
        json: async () => ({
          locator: "artifacts/ms3/source-captures/capture-20260812t120000z-0001020304050607/raw/chunk-0001.webm",
          bytes: 5,
          sha256: "a".repeat(64),
        }),
      };
    },
  });
  const file = {
    name: "extension-capture.webm",
    size: 5,
    type: "audio/webm",
    async arrayBuffer() { return new TextEncoder().encode("hello").buffer; },
  };
  const result = await flow.upload([file], { onProgress: (event) => progress.push(event) });

  assert.equal(result.results.length, 1);
  assert.equal(
    uploads[0].target,
    "/source-captures/capture-20260812t120000z-0001020304050607/raw/chunk-0001.webm",
  );
  assert.equal(uploads[0].init.method, "POST");
  assert.equal(uploads[0].init.headers["Content-Type"], "audio/webm");
  assert.match(uploads[0].init.headers["X-Content-SHA256"], /^[0-9a-f]{64}$/);
  assert.equal(uploads[0].init.body, file);
  assert.deepEqual(progress.map((event) => event.phase), ["uploading", "uploaded"]);

  const appSource = await readFile(new URL("../app.js", import.meta.url), "utf8");
  const htmlSource = await readFile(new URL("../index.html", import.meta.url), "utf8");
  assert.match(appSource, /bindSourceCaptureUpload\(\)/);
  assert.match(appSource, /source-captures\/\$\{captureId\}\/raw/);
  assert.match(htmlSource, /id="source-capture-files"/);
  assert.match(htmlSource, /実録音を追加/);
});
