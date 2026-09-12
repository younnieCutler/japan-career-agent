#!/usr/bin/env python3
"""Regression tests for the local evidence-preserving observation pack."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_observation_pack as pack  # noqa: E402
import run_agent_checks  # noqa: E402

DUMMY_HANDLE = "obs-0123456789abcdef01234567"


class ArchiveContractTests(unittest.TestCase):
    def test_raw_streams_round_trip_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            stdout = b"alpha\n\xffbeta\n"
            stderr = b"warning\r\n"
            receipt = pack.archive_observation(
                label="demo",
                command=("python", "demo.py"),
                returncode=3,
                stdout=stdout,
                stderr=stderr,
                store=store,
            )
            record, restored_stdout, restored_stderr = pack.load_observation(
                receipt.handle or "", store=store
            )
        self.assertEqual(restored_stdout, stdout)
        self.assertEqual(restored_stderr, stderr)
        self.assertEqual(record["stdout_bytes"], len(stdout))
        self.assertEqual(record["stderr_bytes"], len(stderr))

    def test_same_evidence_has_a_stable_handle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            first = pack.archive_observation(
                label="same",
                command=("cmd", "arg"),
                returncode=0,
                stdout=b"ok\n",
                stderr=b"",
                store=store,
            )
            second = pack.archive_observation(
                label="same",
                command=("cmd", "arg"),
                returncode=0,
                stdout=b"ok\n",
                stderr=b"",
                store=store,
            )
        self.assertEqual(first.handle, second.handle)
        self.assertRegex(first.handle or "", r"^obs-[0-9a-f]{24}$")

    def test_label_is_part_of_the_content_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            first = pack.archive_observation(
                label="first",
                command=("cmd",),
                returncode=0,
                stdout=b"same",
                stderr=b"",
                store=store,
            )
            second = pack.archive_observation(
                label="second",
                command=("cmd",),
                returncode=0,
                stdout=b"same",
                stderr=b"",
                store=store,
            )
        self.assertNotEqual(first.handle, second.handle)

    def test_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            receipt = pack.archive_observation(
                label="tamper",
                command=("cmd",),
                returncode=1,
                stdout=b"before\n",
                stderr=b"",
                store=store,
            )
            path = receipt.path
            self.assertIsNotNone(path)
            assert path is not None
            record = json.loads(path.read_text(encoding="utf-8"))
            record["stdout_bytes"] = 999
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaises(pack.ObservationPackError):
                pack.load_observation(receipt.handle or "", store=store)

    def test_invalid_handle_cannot_escape_the_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(pack.ObservationPackError):
                pack.load_observation("../../etc/passwd", store=Path(directory))


class ReceiptTests(unittest.TestCase):
    def test_failure_receipt_quotes_exact_stderr_tail(self) -> None:
        receipt = pack.ObservationReceipt(
            handle=DUMMY_HANDLE,
            label="failing check",
            command=("cmd",),
            returncode=2,
            stdout=b"stdout line\n",
            stderr=b"one\ntwo\nthree\n",
            path=Path("dummy"),
        )
        text = pack.format_compact_receipt(receipt, excerpt_lines=2)
        self.assertIn("exact stderr lines 2-3", text)
        self.assertIn("  two", text)
        self.assertIn("  three", text)
        self.assertNotIn("  one", text)

    def test_line_window_is_one_indexed_and_bounded(self) -> None:
        start, end, lines = pack.line_window(b"a\nb\nc\nd\n", start_line=2, lines=2)
        self.assertEqual((start, end, lines), (2, 3, ["b", "c"]))

    def test_failed_commands_are_always_packable(self) -> None:
        self.assertTrue(
            pack.should_pack(returncode=1, stdout=b"", stderr=b"", threshold_bytes=10_000)
        )

    def test_small_success_can_stay_unpacked(self) -> None:
        self.assertFalse(
            pack.should_pack(returncode=0, stdout=b"ok", stderr=b"", threshold_bytes=10_000)
        )


class CommandExecutionTests(unittest.TestCase):
    @mock.patch.object(pack.subprocess, "run")
    def test_failed_command_is_archived_and_exit_code_preserved(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=["cmd"], returncode=7, stdout=b"out\n", stderr=b"bad\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            receipt = pack.run_command(
                label="failure",
                command=("cmd",),
                store=Path(directory),
                threshold_bytes=999_999,
            )
            self.assertIsNotNone(receipt.handle)
            self.assertTrue((receipt.path or Path("missing")).is_file())
        self.assertEqual(receipt.returncode, 7)

    @mock.patch.object(pack.subprocess, "run")
    def test_small_success_is_not_archived_by_default(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=["cmd"], returncode=0, stdout=b"ok\n", stderr=b""
        )
        with tempfile.TemporaryDirectory() as directory:
            receipt = pack.run_command(
                label="success",
                command=("cmd",),
                store=Path(directory),
                threshold_bytes=1024,
            )
            self.assertIsNone(receipt.handle)
            self.assertEqual(list(Path(directory).iterdir()), [])

    @mock.patch.object(pack.subprocess, "run", side_effect=FileNotFoundError("missing executable"))
    def test_command_start_failure_is_a_bounded_pack_error(self, _run: mock.Mock) -> None:
        with self.assertRaisesRegex(pack.ObservationPackError, "could not start command 'missing'"):
            pack.run_command(label="start failure", command=("missing",))


class AgentCheckWrapperTests(unittest.TestCase):
    @mock.patch.object(run_agent_checks, "run_command")
    def test_no_pack_success_uses_a_nonzero_suppression_threshold(self, run: mock.Mock) -> None:
        run.return_value = pack.ObservationReceipt(
            handle=None,
            label="repository verification matrix",
            command=(sys.executable, "scripts/run_all_checks.py"),
            returncode=0,
            stdout=b"ok",
            stderr=b"",
            path=None,
        )
        with mock.patch.object(sys, "argv", ["run_agent_checks.py", "--no-pack-success"]):
            self.assertEqual(run_agent_checks.main(), 0)
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["threshold_bytes"], sys.maxsize)
        self.assertFalse(kwargs["always_pack"])

    @mock.patch.object(run_agent_checks, "run_command")
    def test_default_wrapper_packs_success_for_exact_recall(self, run: mock.Mock) -> None:
        run.return_value = pack.ObservationReceipt(
            handle=DUMMY_HANDLE,
            label="repository verification matrix",
            command=(sys.executable, "scripts/run_all_checks.py"),
            returncode=0,
            stdout=b"ok",
            stderr=b"",
            path=Path("dummy"),
        )
        with mock.patch.object(sys, "argv", ["run_agent_checks.py"]):
            self.assertEqual(run_agent_checks.main(), 0)
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["threshold_bytes"], 0)
        self.assertTrue(kwargs["always_pack"])


if __name__ == "__main__":
    unittest.main()
