from __future__ import annotations
import pytest
from src.frontend import state

def setup_function():
    state.clear_current_export_job()

def test_set_and_get_job():
    job = state.set_current_export_job(
        job_id="test-123",
        playlist_ids=["p1", "p2"],
        export_format="csv",
        output_path="/tmp/test.csv"
    )
    assert state.get_current_export_job() == job
    assert job["job_id"] == "test-123"
    assert job["cancelled"] is False

def test_mark_cancelled():
    state.set_current_export_job(
        job_id="test-123",
        playlist_ids=["p1"],
        export_format="xlsx",
        output_path="/tmp/test.xlsx"
    )
    assert state.mark_current_export_cancelled() is True
    job = state.get_current_export_job()
    assert job is not None
    assert job["cancelled"] is True

def test_mark_cancelled_no_job():
    assert state.mark_current_export_cancelled() is False

def test_clear_job():
    state.set_current_export_job(
        job_id="test-123",
        playlist_ids=["p1"],
        export_format="xlsx",
        output_path="/tmp/test.xlsx"
    )
    state.clear_current_export_job()
    assert state.get_current_export_job() is None
