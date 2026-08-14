from __future__ import annotations

import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import run_post_rehearsal as post  # noqa: E402
import run_role_mix as role_mix  # noqa: E402


def test_listening_policy_satisfies_shared_index_contract() -> None:
    policy = post.listening_policy()
    item = {
        "age": "",
        "gender": "",
        "text": "評価文",
    }
    hashes = {
        "base": "a" * 64,
        "cv12-standard": "b" * 64,
        post.CANDIDATE_ID: "c" * 64,
    }

    index = role_mix.listening_index(item, hashes=hashes, policy=policy)

    assert index["run_kind"] == policy["run_kind"]
    assert index["variants"][2]["profile_id"] == (
        f"xvc.exp141.{post.CANDIDATE_ID}.listen-now"
    )


def test_hard_curriculum_has_distinct_listener_identity() -> None:
    policy = post.listening_policy(post.HARD_OUTPUT_KIND)

    assert policy["slug"] == "exp146"
    assert policy["candidate_id"] == "cv12-hard-negative-curriculum170"
    assert policy["result_kind"].startswith("liveconv-exp146-")


def test_selective_retention_has_distinct_listener_identity() -> None:
    policy = post.listening_policy(post.SELECTIVE_OUTPUT_KIND)

    assert policy["slug"] == "exp150"
    assert policy["candidate_id"] == "cv12-selective-retention170"
    assert policy["result_kind"].startswith("liveconv-exp150-")


def test_full_converter_retention_changes_only_trainable_target_identity() -> None:
    policy = post.listening_policy(
        post.SELECTIVE_OUTPUT_KIND, post.FULL_CONVERTER_TARGET
    )

    assert policy["slug"] == "exp154"
    assert policy["candidate_id"] == ("cv12-selective-retention-full-converter170")
    assert "42" not in policy["independent_variable"]


def test_full_converter_is_not_admitted_for_other_curricula() -> None:
    try:
        post.listening_policy(post.HARD_OUTPUT_KIND, post.FULL_CONVERTER_TARGET)
    except post.PostRehearsalError as error:
        assert "selective retention" in str(error)
    else:
        raise AssertionError("full converter unexpectedly admitted")


def test_real_reference_adversarial_keeps_selective_lora_identity() -> None:
    policy = post.listening_policy(
        post.SELECTIVE_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
    )

    assert policy["slug"] == "exp158"
    assert policy["candidate_id"] == ("cv12-selective-retention-real-adversarial170")
    assert "authorized original Amitaro" in policy["independent_variable"]


def test_real_reference_adversarial_rejects_full_converter() -> None:
    try:
        post.listening_policy(
            post.SELECTIVE_OUTPUT_KIND,
            post.FULL_CONVERTER_TARGET,
            post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        )
    except post.PostRehearsalError as error:
        assert "selective LoRA69" in str(error)
    else:
        raise AssertionError("adversarial full converter unexpectedly admitted")


def test_upstream_ema_policy_changes_reported_adapter_state() -> None:
    policy = post.listening_policy(
        post.SELECTIVE_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp163"
    assert policy["candidate_id"] == "cv12-selective-real-adversarial-ema170"
    assert "EMA" in policy["independent_variable"]


def test_acoustic_encoder_policy_moves_learning_before_converter() -> None:
    policy = post.listening_policy(
        post.SELECTIVE_OUTPUT_KIND,
        post.ACOUSTIC_ENCODER_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp198"
    assert policy["candidate_id"] == (
        "cv12-selective-acoustic-encoder-real-adversarial-ema170"
    )
    assert "21,521,536" in policy["independent_variable"]


def test_unpaired_human_policy_factorizes_content_and_identity() -> None:
    policy = post.listening_policy(
        post.UNPAIRED_HUMAN_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.FACTORIZED_UNPAIRED_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp203"
    assert policy["candidate_id"] == "human170-factorized-unpaired-ema170"
    assert "unrelated-text Amitaro" in policy["independent_variable"]


def test_unpaired_output_cycle_policy_moves_content_loss_to_final_wav() -> None:
    policy = post.listening_policy(
        post.UNPAIRED_HUMAN_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.OUTPUT_CYCLE_UNPAIRED_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp208"
    assert policy["candidate_id"] == "human170-unpaired-output-cycle-ema170"
    assert "final converted WAV" in policy["independent_variable"]


def test_factorized_loss_uses_source_semantics_and_target_speaker() -> None:
    import torch

    outputs = {
        "pred": torch.tensor([[[1.0, 3.0]]]),
        "pred_sim_feat": torch.tensor([[2.0, 4.0]]),
        "sim_feat": torch.tensor([[1.0, 1.0]]),
    }
    batch = {"ssl_feat": torch.tensor([[[0.0, 1.0]]])}

    losses = post.factorized_unpaired_generator_loss(
        outputs, batch, torch=torch
    )

    assert losses["semantic"].item() == 2.5
    assert losses["speaker"].item() == 5.0
    assert losses["loss"].item() == 2_550.0


def test_output_cycle_loss_backpropagates_from_final_wav(
    monkeypatch,
) -> None:
    import torch

    reconstruction = torch.tensor([[[1.0, 3.0]]], requires_grad=True)
    outputs = {
        "recons": reconstruction,
        "pred_sim_feat": torch.tensor([[2.0, 4.0]]),
        "sim_feat": torch.tensor([[1.0, 1.0]]),
    }
    batch = {"ssl_feat": torch.tensor([[[0.0, 1.0]]])}
    monkeypatch.setattr(
        post,
        "differentiable_whisper_hidden_states",
        lambda semantic_encoder, waveform, *, torch: waveform,
    )

    losses = post.output_cycle_unpaired_generator_loss(
        outputs,
        batch,
        semantic_encoder=object(),
        torch=torch,
    )
    losses["loss"].backward()

    assert losses["output_cycle_content"].item() == 2.5
    assert losses["speaker"].item() == 5.0
    assert losses["loss"].item() == 2_550.0
    assert reconstruction.grad is not None
    assert torch.count_nonzero(reconstruction.grad).item() == 2


def test_differentiable_whisper_frontend_keeps_waveform_gradient() -> None:
    from types import SimpleNamespace

    import numpy as np
    import torch

    class FakeEncoder:
        def __call__(self, *, input_features, attention_mask):
            assert attention_mask.shape == (
                input_features.shape[0],
                input_features.shape[-1],
            )
            return SimpleNamespace(whisper_hidden_states_50hz=input_features)

    semantic_encoder = SimpleNamespace(
        feature_extractor=SimpleNamespace(
            n_fft=4,
            hop_length=2,
            mel_filters=np.asarray(
                [[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]], dtype=np.float32
            ),
        ),
        encoder=FakeEncoder(),
    )
    waveform = torch.linspace(-0.5, 0.5, 16).reshape(1, 1, -1)
    waveform.requires_grad_(True)

    hidden = post.differentiable_whisper_hidden_states(
        semantic_encoder, waveform, torch=torch
    )
    hidden.square().mean().backward()

    assert hidden.shape[1] == 2
    assert waveform.grad is not None
    assert torch.count_nonzero(waveform.grad).item() > 0


def test_output_cycle_frontend_equivalence_rejects_drift(monkeypatch) -> None:
    import torch

    monkeypatch.setattr(
        post,
        "differentiable_whisper_hidden_states",
        lambda semantic_encoder, waveform, *, torch: waveform,
    )
    source = torch.tensor([[[1.0, 2.0]]])

    metrics = post.validate_output_cycle_frontend(
        object(), source, source + 1e-4, torch=torch
    )
    assert metrics["maximum_absolute_hidden_difference"] < 1e-3

    try:
        post.validate_output_cycle_frontend(
            object(), source, source + 0.1, torch=torch
        )
    except post.PostRehearsalError as error:
        assert "frontend mismatch" in str(error)
    else:
        raise AssertionError("drifted output-cycle frontend unexpectedly admitted")


def test_unpaired_human_manifest_does_not_require_predecessor_result(
    tmp_path: Path,
) -> None:
    curriculum = tmp_path / "curriculum.json"
    curriculum.write_text("{}", encoding="utf-8")

    identities = post.source_receipt_identities(
        post.UNPAIRED_HUMAN_OUTPUT_KIND,
        tmp_path / "no-predecessor-result",
        curriculum,
    )

    assert identities["source_result_sha256"] is None
    assert identities["unpaired_human_curriculum_sha256"] == post.sha256_file(
        curriculum
    )


def test_acoustic_encoder_setter_freezes_every_other_module() -> None:
    class FakeModule:
        def train(self, value: bool) -> None:
            self.training = value

    class FakeParameter:
        def __init__(self, count: int) -> None:
            self.count = count
            self.requires_grad = True

        def requires_grad_(self, value: bool) -> None:
            self.requires_grad = value

        def numel(self) -> int:
            return self.count

    selected = FakeParameter(post.EXPECTED_ACOUSTIC_ENCODER_PARAMETERS)
    excluded = FakeParameter(99)

    class FakeModel:
        acoustic_encoder = FakeModule()

        def eval(self) -> None:
            self.training = False

        def named_parameters(self):
            yield "acoustic_encoder.weight", selected
            yield "acoustic_converter.weight", excluded

    trainable = post._set_acoustic_encoder_training_only(FakeModel())

    assert trainable == [selected]
    assert selected.requires_grad is True
    assert excluded.requires_grad is False


def test_jsut_retention_changes_only_easy_data_identity() -> None:
    policy = post.listening_policy(
        post.JSUT_RETENTION_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp171"
    assert policy["candidate_id"] == ("cv12-jsut-retention-real-adversarial-ema170")
    assert "easy85" in policy["independent_variable"]


def test_commonvoice_retention_changes_only_easy_data_identity() -> None:
    policy = post.listening_policy(
        post.COMMONVOICE_RETENTION_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp186"
    assert policy["candidate_id"] == (
        "cv12-commonvoice48-retention-real-adversarial-ema170"
    )
    assert "48 precommitted Common Voice" in policy["independent_variable"]


def test_source36_retention_changes_only_mutable_function_path() -> None:
    policy = post.listening_policy(
        post.COMMONVOICE_RETENTION_OUTPUT_KIND,
        post.SOURCE36_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp194"
    assert policy["candidate_id"] == (
        "cv12-commonvoice48-source36-real-adversarial-ema170"
    )
    assert "36 source-side" in policy["independent_variable"]


def test_existing_adapter_scope_freezes_lora_outside_selected_path() -> None:
    class FakeModule:
        def train(self, value: bool) -> None:
            self.training = value

    class FakeParameter:
        def __init__(self, count: int) -> None:
            self.count = count
            self.requires_grad = True

        def requires_grad_(self, value: bool) -> None:
            self.requires_grad = value

        def numel(self) -> int:
            return self.count

    target = "acoustic_converter.transformer_blocks.0.attn.to_q"
    selected_a = FakeParameter(10)
    selected_b = FakeParameter(14)
    excluded = FakeParameter(99)

    class FakeModel:
        def eval(self) -> None:
            self.training = False

        def named_modules(self):
            yield f"base_model.model.{target}.lora_A.default", FakeModule()
            yield "base_model.model.acoustic_converter.proj_out.lora_A.default", FakeModule()

        def named_parameters(self):
            yield f"base_model.model.{target}.lora_A.default.weight", selected_a
            yield f"base_model.model.{target}.lora_B.default.weight", selected_b
            yield "base_model.model.acoustic_converter.proj_out.lora_A.default.weight", excluded

    trainable = post._set_existing_adapter_scope_training_only(
        FakeModel(),
        {"target_modules": [target], "trainable_parameter_count": 24},
    )

    assert trainable == [selected_a, selected_b]
    assert selected_a.requires_grad is True
    assert selected_b.requires_grad is True
    assert excluded.requires_grad is False


def test_conditioned_retention_changes_only_easy_condition_identity() -> None:
    policy = post.listening_policy(
        post.CONDITIONED_RETENTION_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
    )

    assert policy["slug"] == "exp191"
    assert policy["candidate_id"] == (
        "cv12-conditioned-retention-real-adversarial-ema170"
    )
    assert "17 each clean" in policy["independent_variable"]


def test_paired_pcgrad_has_distinct_listener_identity() -> None:
    policy = post.listening_policy(
        post.SELECTIVE_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.GENERATIVE_OBJECTIVE,
        False,
        post.PCGRAD_PAIRED_OPTIMIZER,
    )

    assert policy["slug"] == "exp176"
    assert policy["candidate_id"] == "cv12-selective-pcgrad85"
    assert "all 170 sources and targets" in policy["independent_variable"]


def test_parameter_anchor_changes_only_exp163_objective_identity() -> None:
    policy = post.listening_policy(
        post.SELECTIVE_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
        post.SEQUENTIAL_OPTIMIZER,
        True,
    )

    assert policy["slug"] == "exp181"
    assert policy["candidate_id"] == (
        "cv12-selective-real-adversarial-anchor-ema170"
    )
    assert "L2-SP" in policy["independent_variable"]


def test_parameter_anchor_requires_exact_exp163_baseline() -> None:
    for manifest_kind, use_ema in (
        (post.SELECTIVE_OUTPUT_KIND, False),
        (post.JSUT_RETENTION_OUTPUT_KIND, True),
    ):
        try:
            post.listening_policy(
                manifest_kind,
                post.LORA69_TARGET,
                post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
                use_ema,
                post.SEQUENTIAL_OPTIMIZER,
                True,
            )
        except post.PostRehearsalError as error:
            assert "exact EXP-163 baseline" in str(error)
        else:
            raise AssertionError("unsupported parameter anchor policy admitted")


def test_source_activity_envelope_changes_only_exp186_objective_identity() -> None:
    policy = post.listening_policy(
        post.COMMONVOICE_RETENTION_OUTPUT_KIND,
        post.LORA69_TARGET,
        post.REAL_REFERENCE_ADVERSARIAL_OBJECTIVE,
        True,
        post.SEQUENTIAL_OPTIMIZER,
        False,
        True,
    )

    assert policy["slug"] == "exp196"
    assert policy["candidate_id"] == (
        "cv12-commonvoice48-source-envelope-real-adversarial-ema170"
    )
    assert "20 ms/10 ms" in policy["independent_variable"]


def test_paired_pcgrad_rejects_ema_or_other_curriculum() -> None:
    for manifest_kind, use_ema in (
        (post.SELECTIVE_OUTPUT_KIND, True),
        (post.JSUT_RETENTION_OUTPUT_KIND, False),
    ):
        try:
            post.listening_policy(
                manifest_kind,
                post.LORA69_TARGET,
                post.GENERATIVE_OBJECTIVE,
                use_ema,
                post.PCGRAD_PAIRED_OPTIMIZER,
            )
        except post.PostRehearsalError as error:
            assert "paired PCGrad" in str(error)
        else:
            raise AssertionError("unsupported paired PCGrad policy admitted")


def test_paired_rows_require_frozen_hard_easy_order() -> None:
    hard = {
        "curriculum_role": "hard",
        "learning_target": post.REPAIR_TARGET,
    }
    easy = {
        "curriculum_role": "easy",
        "learning_target": post.RETENTION_TARGET,
    }

    assert post.paired_hard_easy_rows([hard, easy]) == [(hard, easy)]
    try:
        post.paired_hard_easy_rows([easy, hard])
    except post.PostRehearsalError as error:
        assert "role order" in str(error)
    else:
        raise AssertionError("reversed PCGrad pair unexpectedly admitted")


def test_pcgrad_smoke_keeps_one_complete_hard_easy_pair() -> None:
    manifest = {
        "kind": post.SELECTIVE_OUTPUT_KIND,
        "items": [
            {"curriculum_role": "hard"},
            {"curriculum_role": "easy"},
            {"curriculum_role": "hard"},
        ],
    }

    rows = post.smoke_rows(manifest, post.PCGRAD_PAIRED_OPTIMIZER)

    assert [row["curriculum_role"] for row in rows] == ["hard", "easy"]


def test_parameter_anchor_smoke_exercises_nonzero_distance_step() -> None:
    items = [{"id": "first"}, {"id": "second"}, {"id": "third"}]

    rows = post.smoke_rows(
        {"kind": post.SELECTIVE_OUTPUT_KIND, "items": items},
        parameter_anchor=True,
    )

    assert rows == items[:2]


def test_acoustic_encoder_smoke_exercises_hard_and_easy_roles() -> None:
    items = [
        {"id": "hard", "curriculum_role": "hard"},
        {"id": "easy", "curriculum_role": "easy"},
        {"id": "later", "curriculum_role": "hard"},
    ]

    rows = post.smoke_rows(
        {"kind": post.SELECTIVE_OUTPUT_KIND, "items": items},
        require_hard_easy=True,
    )

    assert rows == items[:2]


def test_pcgrad_projects_only_conflicting_task_components() -> None:
    import torch

    hard = [torch.tensor([1.0, 0.0])]
    easy = [torch.tensor([-1.0, 1.0])]

    merged, metrics = post.project_conflicting_pair(hard, easy, torch=torch)

    assert metrics["conflict"] is True
    assert torch.allclose(merged[0], torch.tensor([0.5, 1.5]))

    aligned, aligned_metrics = post.project_conflicting_pair(
        [torch.tensor([1.0, 0.0])],
        [torch.tensor([2.0, 0.0])],
        torch=torch,
    )
    assert aligned_metrics["conflict"] is False
    assert torch.equal(aligned[0], torch.tensor([3.0, 0.0]))


def test_parameter_anchor_regularizer_uses_control69_distance() -> None:
    import torch

    parameters = [torch.tensor([2.0, -1.0], requires_grad=True)]
    anchors = [torch.tensor([1.0, 1.0])]

    loss, metrics = post.parameter_anchor_regularizer(
        parameters, anchors, torch=torch, coefficient=2.0
    )
    loss.backward()

    assert float(loss.detach()) == 5.0
    assert metrics == {
        "parameter_anchor_loss": 5.0,
        "parameter_anchor_squared_distance": 5.0,
    }
    assert torch.equal(parameters[0].grad, torch.tensor([2.0, -4.0]))


def test_source_activity_envelope_ignores_gain_but_penalizes_timing() -> None:
    import torch

    source = torch.zeros(1, 1, 38400)
    source[..., 8000:24000] = 0.5
    same_timing = source * 0.2
    shifted = torch.zeros_like(source)
    shifted[..., 12000:28000] = 0.1

    same_loss, _ = post.source_activity_envelope_regularizer(
        same_timing, {"source_wav": source}, torch=torch
    )
    shifted_loss, shifted_metrics = post.source_activity_envelope_regularizer(
        shifted, {"source_wav": source}, torch=torch
    )

    assert float(same_loss) < 1e-5
    assert float(shifted_loss) > 1.0
    assert shifted_metrics["source_activity_envelope_distance"] > 0.1


def test_jsut_smoke_exercises_hard_and_diverse_easy_roots() -> None:
    manifest = {
        "kind": post.JSUT_RETENTION_OUTPUT_KIND,
        "items": [
            {"curriculum_role": "hard", "source_root": "source-work"},
            {"curriculum_role": "easy", "source_root": "diverse-work"},
        ],
    }

    rows = post.smoke_rows(manifest)

    assert [row["source_root"] for row in rows] == [
        "source-work",
        "diverse-work",
    ]


def test_commonvoice_smoke_exercises_hard_and_diverse_easy_roots() -> None:
    manifest = {
        "kind": post.COMMONVOICE_RETENTION_OUTPUT_KIND,
        "items": [
            {"curriculum_role": "hard", "source_root": "source-work"},
            {"curriculum_role": "easy", "source_root": "diverse-work"},
        ],
    }

    rows = post.smoke_rows(manifest)

    assert [row["source_root"] for row in rows] == [
        "source-work",
        "diverse-work",
    ]


def test_adapter_ema_matches_pinned_default_update_schedule() -> None:
    import torch

    model = torch.nn.Linear(1, 1, bias=False)
    model.weight.requires_grad_(True)
    tracker = post.AdapterEMA(model, torch)
    for update in range(1, 171):
        with torch.no_grad():
            model.weight.fill_(float(update))
        tracker.update()

    receipt = tracker.receipt()
    assert receipt["calls"] == 170
    assert receipt["copy_updates"] == 11
    assert receipt["moving_average_updates"] == 6
    assert receipt["last_decay"] == 1.0 - 61.0 ** (-2.0 / 3.0)
    assert float(tracker.shadow["weight"].item()) < 161.0
    tracker.copy_to()
    assert torch.equal(model.weight, tracker.shadow["weight"])
