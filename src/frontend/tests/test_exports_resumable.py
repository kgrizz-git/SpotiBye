"""Tests for the resumable export mixin refactoring."""

from __future__ import annotations


from ..screens.adapter_mixins.exports_resumable import ExportsResumableMixin


class FakeBackendClient:
    """Fake backend client for testing."""

    def __init__(self):
        self.job_status = {"status": "in_progress", "continuation_required": True}
        self.step_count = 0

    def step_export_job(self, job_id, cursor, resume_token, max_playlists_per_step):
        self.step_count += 1
        if self.step_count >= 3:
            return {"status": "completed", "continuation_required": False}
        return self.job_status

    def get_export_job_status(self, job_id):
        return self.job_status


class FakeExportsResumableMixin(ExportsResumableMixin):
    """Fake mixin for testing."""

    def __init__(self):
        self.backend_client = FakeBackendClient()
        self.progress_callback = True
        self.progress_messages = []
        self.error_messages = []
        self.persisted_jobs = []

    def _emit_progress(self, message):
        self.progress_messages.append(message)

    def _load_or_create_resumable_job(self, playlist_ids, format, resume_context):
        return {
            "job_id": "test-job-123",
            "current_cursor": "cursor-1",
            "current_resume_token": "token-1",
        }

    def _persist_active_export_job(self, job, playlist_ids, format, resume_context):
        self.persisted_jobs.append(job)

    def _run_with_transient_retry(
        self, operation_name, operation, max_attempts, base_delay
    ):
        return operation()

    def _format_backend_api_error(self, error, context):
        return f"{context}: {str(error)}"

    def error_callback(self, message):
        self.error_messages.append(message)


class TestResumableExportRefactoring:
    """Tests for refactored resumable export functions."""

    def test_validate_resumable_job_fields_success(self):
        """Test successful validation of job fields."""
        mixin = FakeExportsResumableMixin()
        job = {
            "job_id": "test-job",
            "current_cursor": "cursor-1",
            "current_resume_token": "token-1",
        }

        job_id, cursor, token = mixin._validate_resumable_job_fields(job)

        assert job_id == "test-job"
        assert cursor == "cursor-1"
        assert token == "token-1"

    def test_validate_resumable_job_fields_missing_fields(self):
        """Test validation failure with missing fields."""
        mixin = FakeExportsResumableMixin()
        job = {"job_id": "test-job"}  # Missing cursor and token

        job_id, cursor, token = mixin._validate_resumable_job_fields(job)

        assert job_id is None
        assert cursor is None
        assert token is None

    def test_is_job_complete_completed_status(self):
        """Test job completion check with completed status."""
        mixin = FakeExportsResumableMixin()
        status = {"status": "completed"}

        assert mixin._is_job_complete(status) is True

    def test_is_job_complete_continuation_false(self):
        """Test job completion check with continuation_required false."""
        mixin = FakeExportsResumableMixin()
        status = {"status": "in_progress", "continuation_required": False}

        assert mixin._is_job_complete(status) is True

    def test_is_job_complete_in_progress(self):
        """Test job completion check with in-progress status."""
        mixin = FakeExportsResumableMixin()
        status = {"status": "in_progress", "continuation_required": True}

        assert mixin._is_job_complete(status) is False

    def test_update_export_progress_collect_phase(self):
        """Test progress update for collect phase."""
        mixin = FakeExportsResumableMixin()
        status = {
            "processed_count": 5,
            "playlist_count": 10,
            "phase": "collect",
            "current_track_offset": 100,
        }

        mixin._update_export_progress(status, ["playlist1", "playlist2"])

        assert len(mixin.progress_messages) == 1
        assert "collect" in mixin.progress_messages[0]
        assert "5/10" in mixin.progress_messages[0]

    def test_update_export_progress_assemble_phase(self):
        """Test progress update for assemble phase."""
        mixin = FakeExportsResumableMixin()
        status = {
            "processed_count": 10,
            "playlist_count": 10,
            "phase": "assemble",
            "assemble_index": 7,
        }

        mixin._update_export_progress(status, ["playlist1", "playlist2"])

        assert len(mixin.progress_messages) == 1
        assert "assemble" in mixin.progress_messages[0]
        assert "7/10" in mixin.progress_messages[0]

    def test_update_cursor_and_token(self):
        """Test cursor and token update."""
        mixin = FakeExportsResumableMixin()
        status = {
            "current_cursor": "new-cursor",
            "current_resume_token": "new-token",
        }

        new_cursor, new_token = mixin._update_cursor_and_token(
            status, "old-cursor", "old-token"
        )

        assert new_cursor == "new-cursor"
        assert new_token == "new-token"

    def test_update_cursor_and_token_fallback(self):
        """Test cursor and token update with fallback to old values."""
        mixin = FakeExportsResumableMixin()
        status = {}  # No new values

        new_cursor, new_token = mixin._update_cursor_and_token(
            status, "old-cursor", "old-token"
        )

        assert new_cursor == "old-cursor"
        assert new_token == "old-token"

    def test_execute_export_step(self):
        """Test execution of a single export step."""
        mixin = FakeExportsResumableMixin()

        result = mixin._execute_export_step("job-123", "cursor-1", "token-1", 1)

        assert isinstance(result, dict)
        assert mixin.backend_client.step_count == 1

    def test_generate_batch_export_resumable_success(self):
        """Test successful resumable export generation."""
        mixin = FakeExportsResumableMixin()

        result = mixin._generate_batch_export_resumable(
            ["playlist1", "playlist2"],
            "xlsx",
            chunk_size=1,
            max_steps=10,
        )

        assert result is not None
        assert result.get("status") == "completed"
        assert len(mixin.persisted_jobs) > 0

    def test_generate_batch_export_resumable_invalid_job(self):
        """Test resumable export with invalid job response."""
        mixin = FakeExportsResumableMixin()

        def return_invalid_job(*args, **kwargs):
            return None

        mixin._load_or_create_resumable_job = return_invalid_job

        result = mixin._generate_batch_export_resumable(["playlist1"], "xlsx")

        assert result is None
