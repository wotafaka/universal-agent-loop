"""Command line interface: ``python -m agent_loop --project <root> ...``.

Every command operates on the explicit project root only, prints one
machine-readable JSON line, exits 0 on success and 2 with stable
refusal codes on any fail-closed outcome. The CLI is the only ingestion
path for runs, validation occurrences, events, receipts, handoff
results and decisions. Authority operations (engineer launch, owner
adjudication, review seal, acceptance) pass the trusted-config and
registered-session gates defined in agent_loop.authority.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import (attempts, audit, authority, claims, config as _config_mod,
               context, continuation, delivery, envelope, events, handoff,
               lifecycle, observer, packs, reviewgate, runner, taskfile,
               validation)
from .errors import UALError
from .hashing import load_json
from .paths import read_regular_file
from .taskfile import load_task

# Documented hard byte caps for external file transmission: reads happen
# once, contained, before any claim/run/child exists (docs/RUNTIME.md).
STDIN_FILE_MAX_BYTES = 8 * 1024 * 1024
BASIS_FILE_MAX_BYTES = 1024 * 1024


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent_loop",
        description="Provider-neutral Universal Agent Loop runtime. "
                    "All guarantees are LOCAL_INTEGRITY.")
    parser.add_argument("--project", required=True,
                        help="Target project root (never this package).")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("task-validate")
    p.add_argument("--task", required=True)

    p = sub.add_parser("session")
    session_sub = p.add_subparsers(dest="session_command", required=True)
    p2 = session_sub.add_parser("register")
    p2.add_argument("--actor", required=True)
    p2.add_argument("--role", required=True)
    p2.add_argument("--transport", required=True)
    p2.add_argument("--session-id", required=True)
    p2.add_argument("--origin", default="controller")

    p = sub.add_parser("route")
    route_sub = p.add_subparsers(dest="route_command", required=True)
    p2 = route_sub.add_parser("check")
    p2.add_argument("--role", required=True)

    p = sub.add_parser("attempt")
    attempt_sub = p.add_subparsers(dest="attempt_command", required=True)
    p2 = attempt_sub.add_parser("open")
    p2.add_argument("--task", required=True)
    p2.add_argument("--batch", default=None)
    p2.add_argument("--claim-file", default=None)
    p2.add_argument("--efficiency-ack", action="append", default=[])
    p2.add_argument("--consume-pending", default=None, metavar="TASK",
                    help="Consume a predecessor task's pending efficiency "
                         "decisions before opening.")
    p2.add_argument("--pack-iteration", type=int, default=None,
                    help="Bind this attempt to a verified repair pack "
                         "iteration (verify-first).")

    p = sub.add_parser("checkpoint")
    checkpoint_sub = p.add_subparsers(dest="checkpoint_command",
                                      required=True)
    p2 = checkpoint_sub.add_parser("save")
    p2.add_argument("--task", required=True)
    p2.add_argument("--phase", required=True)
    p2 = checkpoint_sub.add_parser("verify")
    p2.add_argument("--task", required=True)

    p = sub.add_parser("usage")
    usage_sub = p.add_subparsers(dest="usage_command", required=True)
    p2 = usage_sub.add_parser("record")
    p2.add_argument("--task", required=True)
    p2.add_argument("--run", required=True)
    p2.add_argument("--usage-file", required=True)

    p = sub.add_parser("inventory")

    p = sub.add_parser("install")
    install_sub = p.add_subparsers(dest="install_command", required=True)
    for name in ("plan", "dry-run", "apply", "doctor"):
        p2 = install_sub.add_parser(name)
        p2.add_argument("--source", required=True)
        p2.add_argument("--target", required=True)

    p = sub.add_parser("handoff")
    handoff_sub = p.add_subparsers(dest="handoff_command", required=True)
    p2 = handoff_sub.add_parser("issue")
    p2.add_argument("--task", required=True)
    p2.add_argument("--session-id", required=True)
    p2 = handoff_sub.add_parser("receive")
    p2.add_argument("--task", required=True)
    p2.add_argument("--request", required=True)
    p2.add_argument("--result-file", required=True)
    p2.add_argument("--session-id", required=True)
    p2 = handoff_sub.add_parser("confirm")
    p2.add_argument("--task", required=True)
    p2.add_argument("--request", required=True)
    p2.add_argument("--actor", required=True)
    p2.add_argument("--decision", required=True)

    p = sub.add_parser("status")
    status_sub = p.add_subparsers(dest="status_command", required=True)
    p2 = status_sub.add_parser("set")
    p2.add_argument("--task", required=True)
    p2.add_argument("--status", required=True)

    p = sub.add_parser("claim")
    claim_sub = p.add_subparsers(dest="claim_command", required=True)
    p2 = claim_sub.add_parser("acquire")
    p2.add_argument("--task", required=True)
    p2 = claim_sub.add_parser("scan")
    p2 = claim_sub.add_parser("bind-child")
    p2.add_argument("--claim-id", required=True)
    p2.add_argument("--pid", type=int, required=True)
    p2.add_argument("--identity-state", required=True)
    p2.add_argument("--identity-method", default=None)
    p2.add_argument("--identity-value", default=None)
    p2 = claim_sub.add_parser("release")
    p2.add_argument("--claim-id", required=True)
    p2.add_argument("--run", required=True)
    p2 = claim_sub.add_parser("abandon")
    p2.add_argument("--claim-id", required=True)
    p2.add_argument("--actor", required=True)
    p2.add_argument("--reason", required=True)

    p = sub.add_parser("run")
    p.add_argument("--task", required=True)
    p.add_argument("--purpose", required=True)
    p.add_argument("--argv-json", default=None)
    p.add_argument("--stdin-file", default=None,
                   help="Contained regular file read before any claim/"
                        "run exists; hard cap 8 MiB. ENGINEER stdin must "
                        "be a task-authorized pack and pass the secret "
                        "scan.")
    p.add_argument("--ack-path", default=None)
    p.add_argument("--session-id", default=None)
    p.add_argument("--basis-file", default=None,
                   help="Contained regular progress-basis file read "
                        "before any claim/run exists; hard cap 1 MiB.")
    p.add_argument("--log-cap-bytes", type=int,
                   default=runner.DEFAULT_LOG_CAP_BYTES)
    p.add_argument("--env-overlay-json", default=None)
    p.add_argument("--env-base-json", default=None)

    p = sub.add_parser("validate")
    validate_sub = p.add_subparsers(dest="validate_command", required=True)
    p2 = validate_sub.add_parser("record")
    p2.add_argument("--task", required=True)
    p2.add_argument("--run", required=True)
    p2.add_argument("--ordinal", type=int, required=True)
    p2.add_argument("--seed", default=None)
    p2 = validate_sub.add_parser("status")
    p2.add_argument("--task", required=True)

    p = sub.add_parser("event")
    event_sub = p.add_subparsers(dest="event_command", required=True)
    p2 = event_sub.add_parser("record")
    p2.add_argument("--task", required=True)
    p2.add_argument("--tool", required=True)
    p2.add_argument("--detail", default="")
    p2.add_argument("--exit", dest="exit_code", type=int, default=None)
    p2 = event_sub.add_parser("ingest-export")
    p2.add_argument("--task", required=True)
    p2.add_argument("--file", required=True)
    p2.add_argument("--attested-by", default=None)

    p = sub.add_parser("lessons")
    lessons_sub = p.add_subparsers(dest="lessons_command", required=True)
    p2 = lessons_sub.add_parser("record")
    p2.add_argument("--task", required=True)
    p2.add_argument("--finding", required=True)
    p2.add_argument("--text", required=True)
    p2 = lessons_sub.add_parser("promote")
    p2.add_argument("--task", required=True)
    p2.add_argument("--finding", required=True)
    p2.add_argument("--to", required=True)

    p = sub.add_parser("refresh")
    p.add_argument("--task", required=True)

    p = sub.add_parser("report-check")
    p.add_argument("--task", required=True)

    p = sub.add_parser("close")
    p.add_argument("--task", required=True)

    p = sub.add_parser("envelope")
    envelope_sub = p.add_subparsers(dest="envelope_command", required=True)
    p2 = envelope_sub.add_parser("freeze")
    p2.add_argument("--task", required=True)
    p2 = envelope_sub.add_parser("verify")
    p2.add_argument("--task", required=True)

    p = sub.add_parser("review")
    review_sub = p.add_subparsers(dest="review_command", required=True)
    p2 = review_sub.add_parser("validate")
    p2.add_argument("--task", required=True)
    p2.add_argument("--review", required=True)
    p2.add_argument("--reviewer-session", default=None)
    p2.add_argument("--reference-root", default=None)
    p2 = review_sub.add_parser("seal")
    p2.add_argument("--task", required=True)
    p2.add_argument("--review", required=True)
    p2.add_argument("--verdict", default="PASS")
    p2.add_argument("--reviewer-session", default=None)

    p = sub.add_parser("accept")
    p.add_argument("--task", required=True)
    p.add_argument("--actor", required=True)
    p.add_argument("--decision", required=True)
    p.add_argument("--review", required=True)

    p = sub.add_parser("observer")
    observer_sub = p.add_subparsers(dest="observer_command", required=True)
    p2 = observer_sub.add_parser("policy")
    p2.add_argument("--task", required=True)
    p2 = observer_sub.add_parser("record")
    p2.add_argument("--task", required=True)
    p2.add_argument("--payload", required=True)

    p = sub.add_parser("audit")
    audit_sub = p.add_subparsers(dest="audit_command", required=True)
    p2 = audit_sub.add_parser("package")
    p2.add_argument("--task", required=True)
    p2.add_argument("--iteration", type=int, required=True)
    p2.add_argument("--input", action="append", default=[])
    p2.add_argument("--instruction", action="append", default=[])
    p2.add_argument("--validation", action="append", default=[])
    p2 = audit_sub.add_parser("verify")
    p2.add_argument("--task", required=True)
    p2.add_argument("--package", required=True)
    p2 = audit_sub.add_parser("record")
    p2.add_argument("--task", required=True)
    p2.add_argument("--package", required=True)
    p2.add_argument("--result-file", required=True)
    p2.add_argument("--route-receipt", default=None,
                    help="Bound ual-audit-route-receipt/1 file; required "
                         "when a primary auditor is configured.")
    p2.add_argument("--allow-fallback", action="store_true")
    p2 = audit_sub.add_parser("route-receipt")
    p2.add_argument("--task", required=True)
    p2.add_argument("--package", required=True)
    p2.add_argument("--kind", required=True,
                    help="AUDIT_RESULT or PROVIDER_FAILURE")
    p2.add_argument("--requested-model", required=True)
    p2.add_argument("--model-observed", required=True)
    p2.add_argument("--exit-code", type=int, required=True)
    p2.add_argument("--status", default="FINISHED")
    p2.add_argument("--result-file", default=None)
    p2.add_argument("--raw-error-file", default=None)
    p2.add_argument("--provider-status", type=int, default=None)
    p2.add_argument("--error-code", default=None)
    p2.add_argument("--terminal", action="store_true")
    p2.add_argument("--out", required=True)
    p2 = audit_sub.add_parser("quota-receipt")
    p2.add_argument("--task", required=True)
    p2.add_argument("--package", required=True)
    p2.add_argument("--reason", required=True)
    p2.add_argument("--route-receipt", default=None,
                    help="Bound primary PROVIDER_FAILURE route receipt "
                         "with structured terminal quota evidence.")
    p2 = audit_sub.add_parser("status")
    p2.add_argument("--task", required=True)

    p = sub.add_parser("pack")
    pack_sub = p.add_subparsers(dest="pack_command", required=True)
    p2 = pack_sub.add_parser("build")
    p2.add_argument("--task", required=True)
    p2.add_argument("--iteration", type=int, required=True)
    p2.add_argument("--batch", required=True)
    p2.add_argument("--touched", required=True)
    p2 = pack_sub.add_parser("verify")
    p2.add_argument("--task", required=True)
    p2.add_argument("--iteration", type=int, required=True)

    p = sub.add_parser("progress")
    progress_sub = p.add_subparsers(dest="progress_command", required=True)
    p2 = progress_sub.add_parser("check")
    p2.add_argument("--task", required=True)
    p2.add_argument("--batch", required=True)
    p2.add_argument("--claim-file", default=None)

    p = sub.add_parser("continuation")
    cont_sub = p.add_subparsers(dest="continuation_command", required=True)
    p2 = cont_sub.add_parser("prepare")
    p2.add_argument("--task", required=True)
    p2 = cont_sub.add_parser("verify")
    p2.add_argument("--task", required=True)

    p = sub.add_parser("context")
    ctx_sub = p.add_subparsers(dest="context_command", required=True)
    p2 = ctx_sub.add_parser("build")
    p2.add_argument("--task", required=True)
    p2 = ctx_sub.add_parser("verify")
    p2.add_argument("--task", required=True)
    p2.add_argument("--pack", required=True)
    p2 = ctx_sub.add_parser("retrieve")
    p2.add_argument("--task", required=True)
    p2.add_argument("--need", required=True)
    p2.add_argument("--run", required=True)

    p = sub.add_parser("release")
    release_sub = p.add_subparsers(dest="release_command", required=True)
    for name in ("build", "verify"):
        p2 = release_sub.add_parser(name)
        p2.add_argument("--allowlist", required=True)
        p2.add_argument("--release-root", default=".",
                        help="Root the allowlist paths resolve against "
                             "(default: the project root).")
        if name == "build":
            p2.add_argument("--out-zip", required=True)
            p2.add_argument("--out-manifest", required=True)
        else:
            p2.add_argument("--archive", required=True)
            p2.add_argument("--manifest", required=True)

    p = sub.add_parser("report")
    report_sub = p.add_subparsers(dest="report_command", required=True)
    p2 = report_sub.add_parser("efficiency")
    p2.add_argument("--task", required=True)
    p2.add_argument("--dispositions", default=None)
    p2 = report_sub.add_parser("delivery")
    p2.add_argument("--task", required=True)
    p2 = report_sub.add_parser("checkpoint")
    p2.add_argument("--task", required=True)
    p2.add_argument("--run", required=True)
    p2.add_argument("--kind", required=True)
    p2.add_argument("--seconds", type=float, required=True)

    return parser


def _load_task_for(project: Path, task_rel: str) -> dict:
    task_path = Path(project) / task_rel
    task = load_task(task_path)
    errors = taskfile.validate_task(task)
    if errors:
        raise UALError("TASK_INVALID", ";".join(errors[:4]))
    return task


def _gate_closed(project: Path, task: dict) -> None:
    if lifecycle.closed_record(project, task) is None:
        return
    if envelope.acceptance_record(project, task["id"]) is not None:
        return
    raise UALError("POST_CLOSE_RUN", task["id"])


def _record_engineer_session(project: Path, task_id: str, session_id):
    state = lifecycle.ensure_state(project, task_id)
    state["engineer_session"] = session_id
    lifecycle.save_state(project, task_id, state)


def _engineer_launch_gate(project: Path, task: dict, session_id) -> dict:
    """Prelaunch composition gate for a paid engineer launch: trusted
    authority config, a registered ENGINEER session, attempt
    authorization and verified continuation — shared with the native
    handoff path — plus the command-transport route check, all before
    any claim, log file or child exists."""
    gate = attempts.prelaunch(project, task, session_id)
    config = gate["config"]
    role_class, binding = authority.engineer_binding(config, task)
    if not isinstance(binding, dict) or \
            binding.get("transport") not in ("command", "native"):
        raise UALError("ROUTE_UNUSABLE",
                       f"no usable binding for {role_class}")
    gate["role_class"] = role_class
    gate["binding"] = binding
    return gate


def _dispatch(args, project: Path) -> dict:
    if args.command == "task-validate":
        task = _load_task_for(project, args.task)
        config = authority.load_config(project)
        if config is not None and \
                task.get("owner_actor") != config.get("owner_actor"):
            raise UALError("TASK_OWNER_ACTOR_UNCONFIGURED",
                           f"{task.get('owner_actor')} not the configured "
                           f"owner actor")
        return {"ok": True, "task": task["id"], "mode": task["mode"],
                "risk": task["risk"],
                "requirements": len(task.get("requirements") or [])}
    if args.command == "session":
        return authority.register_session(
            project, args.actor, args.role, args.transport,
            args.session_id, args.origin)
    if args.command == "route":
        return authority.route_check(project, args.role)
    if args.command == "attempt":
        task = _load_task_for(project, "task.json")
        return attempts.open_attempt(project, task, args.batch,
                                     args.claim_file, args.efficiency_ack,
                                     args.consume_pending,
                                     args.pack_iteration)
    if args.command == "checkpoint":
        task = _load_task_for(project, "task.json")
        if args.checkpoint_command == "save":
            return attempts.save_checkpoint(project, task, args.phase)
        return attempts.verify_checkpoint(project, task)
    if args.command == "usage":
        task = _load_task_for(project, "task.json")
        usage = load_json(project / args.usage_file, max_bytes=64 * 1024)
        if not isinstance(usage, dict):
            raise UALError("USAGE_MALFORMED", args.usage_file)
        return delivery.record_usage_receipt(project, task, args.run, usage)
    if args.command == "inventory":
        return _inventory(project)
    if args.command == "install":
        from .installer import plan_install, dry_run, apply_install, \
            doctor
        source = Path(args.source).resolve(strict=False)
        target = Path(args.target).resolve(strict=False)
        if args.install_command == "plan":
            return plan_install(source, target)
        if args.install_command == "dry-run":
            return dry_run(source, target)
        if args.install_command == "apply":
            return apply_install(source, target)
        return doctor(source, target)
    if args.command == "handoff":
        task = _load_task_for(project, "task.json")
        if args.handoff_command == "issue":
            payload = handoff.issue(project, task, args.session_id)
            _record_engineer_session(project, task["id"], args.session_id)
            return payload
        if args.handoff_command == "receive":
            return handoff.receive(project, task, args.request,
                                   args.result_file, args.session_id)
        return handoff.confirm(project, task, args.request, args.actor,
                               args.decision)
    if args.command == "status":
        return lifecycle.set_status(project, args.task, args.status)
    if args.command == "claim":
        if args.claim_command == "acquire":
            result = claims.acquire(project, args.task)
            lifecycle.ensure_state(project, args.task)
            return {"ok": True, "claim_id": result["claim_id"],
                    "path": str(result["path"]),
                    "sequence": result["sequence"],
                    "task": args.task}
        if args.claim_command == "scan":
            entries = claims.scan_claims(project)
            return {"ok": True, "claims": [
                dict(record, name=path.name) for path, record in entries]}
        if args.claim_command == "bind-child":
            identity = None
            if args.identity_state == claims.IDENTITY_OBTAINED:
                identity = {"method": args.identity_method or "",
                            "value": args.identity_value or ""}
            claims.bind_child(project, args.claim_id, args.pid, identity,
                              args.identity_state)
            return {"ok": True}
        if args.claim_command == "release":
            loader = runner._sidecar_loader(project)
            result = claims.release(project, args.claim_id, args.run,
                                    loader)
            return {"ok": True, "status": result["status"]}
        if args.claim_command == "abandon":
            authority.require_actor_role(project, args.actor, "OWNER")
            claim = claims.abandon(project, args.claim_id, args.actor,
                                   args.reason)
            return {"ok": True, "status": claim["status"]}
    if args.command == "run":
        task = _load_task_for(project, "task.json")
        if task["id"] != args.task:
            raise UALError("TASK_MISMATCH", f"{task['id']}!={args.task}")
        _gate_closed(project, task)
        declared_commands = taskfile.validation_commands(task)
        if args.purpose == "ENGINEER":
            gate = _engineer_launch_gate(project, task, args.session_id)
            if gate["binding"].get("transport") == "native":
                raise UALError("NATIVE_HANDOFF_REQUIRED",
                               "the configured engineer transport is "
                               "native; use handoff issue")
            binding_argv = gate["binding"].get("argv") or []
            if args.argv_json is not None and \
                    json.loads(args.argv_json) != binding_argv:
                raise UALError("ENGINEER_ARGV_NOT_CONFIGURED",
                               "the engineer adapter is the trusted "
                               "configured binding, not caller argv")
            if args.env_overlay_json or args.env_base_json:
                raise UALError("ENGINEER_ENV_NOT_CONFIGURED",
                               "engineer environment policy comes from the "
                               "task and trusted config, not overrides")
            argv = list(binding_argv)
        else:
            argv = json.loads(args.argv_json)
            if args.purpose == "VALIDATION" and not any(
                    c["argv"] == argv for c in declared_commands):
                raise UALError("VALIDATION_ARGV_NOT_DECLARED",
                               "validation runs must use a declared task "
                               "command")
        overlay = json.loads(args.env_overlay_json) if \
            args.env_overlay_json else None
        if args.env_base_json and args.purpose != "ENGINEER":
            task = dict(task)
            task["validation"] = dict(
                task.get("validation") or {})
            task["validation"]["environment"] = {
                "base": json.loads(args.env_base_json),
                "overlay": (task["validation"].get("environment")
                            or {}).get("overlay") or {}}
        stdin_bytes = b""
        if args.stdin_file:
            stdin_bytes = read_regular_file(
                project, args.stdin_file, label="STDIN",
                max_bytes=STDIN_FILE_MAX_BYTES)
            if args.purpose == "ENGINEER":
                packs.verify_engineer_stdin(project, task["id"],
                                            args.stdin_file, stdin_bytes)
        basis_text = None
        if args.basis_file:
            basis_raw = read_regular_file(
                project, args.basis_file, label="BASIS",
                max_bytes=BASIS_FILE_MAX_BYTES)
            try:
                basis_text = basis_raw.decode("utf-8")
            except UnicodeDecodeError:
                raise UALError("BASIS_UNREADABLE",
                               args.basis_file) from None
        payload = runner.run_child(
            project, task, purpose=args.purpose, argv=argv,
            stdin_bytes=stdin_bytes, overlay=overlay,
            ack_rel=args.ack_path, session_id=args.session_id,
            log_cap_bytes=args.log_cap_bytes,
            basis_text=basis_text)
        if args.purpose == "ENGINEER":
            _record_engineer_session(project, task["id"], args.session_id)
        return payload
    if args.command == "validate":
        task = _load_task_for(project, "task.json")
        if args.validate_command == "record":
            if lifecycle.closed_record(project, task) is not None and \
                    envelope.acceptance_record(project,
                                               task["id"]) is None:
                raise UALError("POST_CLOSE_RECORD", args.run)
            return validation.record_occurrence(
                project, task, args.run, args.ordinal, args.seed)
        if args.validate_command == "status":
            ledger = validation.Ledger(project, task)
            return {"ok": True, "task": task["id"],
                    "declared": [c["argv"] for c in
                                 taskfile.validation_commands(task)],
                    "occurrences": len(ledger.occurrences),
                    "evidence_state": validation.evidence_state(ledger)}
    if args.command == "event":
        task = _load_task_for(project, "task.json")
        if args.event_command == "record":
            return events.record_event(project, task, args.tool,
                                       args.detail, args.exit_code)
        return events.ingest_export(project, task, args.file,
                                    args.attested_by)
    if args.command == "lessons":
        task = _load_task_for(project, "task.json")
        if args.lessons_command == "record":
            return _record_lesson(project, task, args.finding, args.text)
        return _promote_lesson(project, task, args.finding, args.to)
    if args.command == "refresh":
        return lifecycle.refresh(project, _load_task_for(project,
                                                         "task.json"))
    if args.command == "report-check":
        return lifecycle.report_check(project, _load_task_for(
            project, "task.json"))
    if args.command == "close":
        task = _load_task_for(project, "task.json")
        return lifecycle.close(project, task, observer_gate=lambda:
                               observer.gate_errors(project, task))
    if args.command == "envelope":
        task = _load_task_for(project, "task.json")
        attempts.ensure_current(project, task)
        if args.envelope_command == "freeze":
            return envelope.freeze_envelope(project, task)
        return envelope.verify_envelope(project, task)
    if args.command == "review":
        task = _load_task_for(project, "task.json")
        review_path = project / args.review
        if not review_path.is_file():
            raise UALError("REVIEW_ARTIFACT_UNREADABLE", args.review)
        text = review_path.read_text(encoding="utf-8")
        if args.review_command == "validate":
            if envelope.latest_envelope(project, task["id"]) is not None:
                envelope.verify_envelope(project, task)
            refusals = reviewgate.validate_review(
                text, project, task, reference_root=args.reference_root)
            if args.reviewer_session:
                session = authority.require_session_role(
                    project, args.reviewer_session, "REVIEWER")
                state = lifecycle.load_state(project, task["id"]) or {}
                engineer = state.get("engineer_session")
                if engineer and engineer == args.reviewer_session:
                    refusals.append("REVIEWER_SESSION_NOT_DISTINCT:"
                                    + str(engineer))
            if refusals:
                raise UALError("REVIEW_REFUSED", ";".join(refusals[:4]))
            return {"ok": True, "refusals": []}
        return envelope.write_review_seal(project, task, args.review,
                                          args.verdict,
                                          args.reviewer_session)
    if args.command == "accept":
        task = _load_task_for(project, "task.json")
        return envelope.accept(project, task, args.actor, args.decision,
                               args.review)
    if args.command == "observer":
        if args.observer_command == "policy":
            task = load_task(project / "task.json")
            if not isinstance(task, dict) or \
                    task.get("schema") != taskfile.TASK_SCHEMA:
                raise UALError("TASK_SCHEMA_UNKNOWN", args.task)
            decision = observer.decide_observer_policy(task)
            return {"ok": True, **decision}
        task = _load_task_for(project, "task.json")
        attempts.ensure_current(project, task)
        payload = load_json(project / args.payload, max_bytes=64 * 1024)
        return observer.record_receipt(project, task, payload)
    if args.command == "audit":
        task = _load_task_for(project, "task.json")
        if args.audit_command == "package":
            roles = {"input": args.input, "instruction": args.instruction,
                     "validation": args.validation}
            return audit.build_package(project, task, args.iteration,
                                       roles)
        if args.audit_command == "verify":
            return audit.verify_package(project, task["id"],
                                        args.package)
        if args.audit_command == "record":
            return audit.record_audit(project, task, args.package,
                                      args.result_file,
                                      args.route_receipt,
                                      args.allow_fallback)
        if args.audit_command == "route-receipt":
            return audit.record_route_receipt(
                project, task, args.package, args.kind,
                args.requested_model, args.model_observed,
                args.exit_code, args.status, args.out,
                result_rel=args.result_file,
                raw_error_rel=args.raw_error_file,
                provider_status=args.provider_status,
                error_code=args.error_code,
                terminal=args.terminal)
        if args.audit_command == "quota-receipt":
            return audit.record_quota_receipt(project, task, args.package,
                                              args.reason,
                                              args.route_receipt)
        return audit.audit_status(project, task["id"])
    if args.command == "pack":
        task = _load_task_for(project, "task.json")
        if args.pack_command == "build":
            return packs.build_pack(project, task, args.iteration,
                                    args.batch, args.touched)
        return packs.verify_pack(project, task["id"], args.iteration)
    if args.command == "progress":
        task = _load_task_for(project, "task.json")
        return packs.progress_gate(project, task, args.batch,
                                   args.claim_file)
    if args.command == "continuation":
        task = _load_task_for(project, "task.json")
        if args.continuation_command == "prepare":
            return continuation.prepare(project, task)
        return continuation.verify(project, task)
    if args.command == "context":
        task = _load_task_for(project, "task.json")
        if args.context_command == "build":
            return context.build_pack(project, task)
        if args.context_command == "retrieve":
            return context.retrieve(project, task, args.need, args.run)
        return context.verify_pack(project, task, args.pack)
    if args.command == "release":
        from . import release as release_mod
        release_root = (project / args.release_root).resolve(strict=False)
        if args.release_command == "build":
            return release_mod.build_release(
                release_root, args.allowlist,
                project / args.out_zip, project / args.out_manifest)
        return release_mod.verify_release(
            release_root, args.allowlist,
            project / args.archive, project / args.manifest)
    if args.command == "report":
        task = _load_task_for(project, "task.json")
        if args.report_command == "efficiency":
            return delivery.efficiency_report(project, task,
                                              args.dispositions)
        if args.report_command == "checkpoint":
            return delivery.record_checkpoint(project, task, args.run,
                                              args.kind, args.seconds)
        return delivery.delivery_report(project, task)
    raise UALError("COMMAND_UNKNOWN", args.command)


def _record_lesson(project: Path, task: dict, finding: str, text: str):
    from .paths import resolve_inside
    from .hashing import sha256_hex
    lessons_rel = task.get("lessons_path") or ".agent-loop/lessons.md"
    lessons_path = resolve_inside(project, lessons_rel, label="LESSONS")
    lessons_path.parent.mkdir(parents=True, exist_ok=True)
    if lessons_path.is_file() and \
            lessons_path.stat().st_size > 256 * 1024:
        raise UALError("LESSONS_OVER_BOUND", lessons_rel)
    if not lessons_path.is_file():
        lessons_path.write_text("# Durable lessons (bounded)\n\n",
                                encoding="utf-8")
    with lessons_path.open("a", encoding="utf-8") as handle:
        handle.write(f"- {finding}: {text}\n")
    return {"ok": True, "path": lessons_rel, "anchor": finding,
            "sha256": sha256_hex(lessons_path.read_bytes())}


def _promote_lesson(project: Path, task: dict, finding: str,
                    target_rel: str):
    """Explicit, traceable promotion of a project-scoped lesson into a
    reusable file. Memory stays project-scoped and evidence-backed by
    default; this is the only path that widens it."""
    from .paths import resolve_inside
    from .hashing import sha256_hex, exclusive_write_json
    from .attempts import current_dir, ensure_current
    from .claims import utc_now_iso
    ensure_current(project, task)
    lessons_rel = task.get("lessons_path") or ".agent-loop/lessons.md"
    lessons_path = resolve_inside(project, lessons_rel, label="LESSONS")
    if not lessons_path.is_file():
        raise UALError("LESSONS_SOURCE_MISSING", lessons_rel)
    lessons_bytes = lessons_path.read_bytes()
    if f"- {finding}:" not in lessons_bytes.decode("utf-8",
                                                   errors="replace"):
        raise UALError("LESSONS_FINDING_MISSING", finding)
    target_path = resolve_inside(project, target_rel, label="PROMOTION")
    existed_before = target_path.is_file()
    target_bytes = target_path.read_bytes() if existed_before else b""
    line = f"- GLOBAL {finding} (from {lessons_rel}): promoted\n"
    if line not in target_bytes.decode("utf-8", errors="replace"):
        with target_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    directory = current_dir(project, task["id"]) / "promotions"
    directory.mkdir(parents=True, exist_ok=True)
    record_path = directory / f"promotion_{finding}.json"
    try:
        exclusive_write_json(record_path, {
            "schema": "ual-lesson-promotion/1",
            "task": task["id"],
            "finding": finding,
            "source": {"path": lessons_rel,
                       "sha256": sha256_hex(lessons_bytes)},
            "target": {"path": target_rel,
                       "sha256": sha256_hex(target_path.read_bytes())},
            "existed_before": existed_before,
            "promoted_at": utc_now_iso(),
        }, max_bytes=64 * 1024)
    except UALError as exc:
        if exc.code == "TARGET_EXISTS":
            raise UALError("PROMOTION_EXISTS", finding)
        raise
    return {"ok": True, "finding": finding, "target": target_rel,
            "record": str(record_path)}


def _inventory(project: Path) -> dict:
    """Expose duplicate instructions/skills/tools by content hash and
    count external connectors (default zero)."""
    hashes: dict = {}
    scan_roots = []
    for rel in ("skills", "templates", "prompts"):
        candidate = project / rel
        if candidate.is_dir():
            scan_roots.append(candidate)
    for rel in ("AGENTS.md", "CLAUDE.md"):
        candidate = project / rel
        if candidate.is_file():
            _inventory_file(candidate, project, hashes)
    for root in scan_roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.stat().st_size <= 1024 * 1024:
                _inventory_file(path, project, hashes)
    duplicate_groups = [
        {"sha256": digest, "paths": sorted(paths)}
        for digest, paths in sorted(hashes.items())
        if len(paths) > 1]
    connectors = 0
    config_file = project / ".agent-loop" / "config.json"
    if config_file.is_file():
        try:
            cfg = load_json(config_file, max_bytes=64 * 1024)
            connectors = len((cfg or {}).get("external_connectors") or {})
        except UALError:
            connectors = 0
    return {"ok": True, "duplicate_groups": duplicate_groups,
            "external_connectors": connectors,
            "note": "runtime defaults to zero external connectors; "
                    "memory is project-scoped unless explicitly promoted"}


def _inventory_file(path: Path, project: Path, hashes: dict) -> None:
    from .hashing import sha256_hex
    digest = sha256_hex(path.read_bytes())
    hashes.setdefault(digest, []).append(
        path.relative_to(project).as_posix())


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = _build_parser()
    args = parser.parse_args(argv)
    project = Path(args.project).resolve(strict=False)
    if not project.is_dir():
        print(json.dumps({"ok": False,
                          "errors": ["PROJECT_ROOT_NOT_A_DIRECTORY:"
                                     + str(project)]}))
        return 2
    try:
        payload = _dispatch(args, project)
    except UALError as exc:
        body = {"ok": False, "errors": [exc.refusal()]}
        if exc.code == "PACK_VERIFY_REFUSED":
            body["fallback"] = "FULL_CANONICAL_STARTUP"
        print(json.dumps(body))
        return 2
    print(json.dumps(payload, ensure_ascii=True))
    return 0
