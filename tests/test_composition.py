import json
import os
import tempfile
import unittest

from rigyd.cli import build_parser
from rigyd.client import RigydClient
from rigyd.composition import Composition


class RecordingClient(RigydClient):
    def __init__(self):
        super().__init__("https://api.example.test", "test-key")
        self.calls = []

    def _request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return {"data": {"id": "composition-1", "workflow": {"status": "running"}}}


class WorkflowClient:
    def __init__(self):
        self.responses = [
            {"id": "composition-1", "workflow": {
                "status": "running", "stage": "planning", "progress": 20}},
            {"id": "composition-1", "workflow": {
                "status": "completed", "stage": "simready_conversion", "progress": 100},
             "conversion_job_id": "job-1"},
        ]

    def get_composition(self, _composition_id):
        return self.responses.pop(0)

    def get_job(self, job_id):
        return {"id": job_id, "status": "completed", "progress": 100}


class CompositionTests(unittest.TestCase):
    def test_json_submission_preserves_composer_parameters(self):
        client = RecordingClient()
        client.create_composition(
            "desktop stapler",
            "press the upper arm",
            asset_class="articulated",
            auto_submit=True,
            physical_context={"mass_kg": 0.3},
        )
        method, path, kwargs = client.calls[0]
        self.assertEqual((method, path), ("POST", "/compositions/generate"))
        payload = json.loads(kwargs["body"])
        self.assertEqual(payload["robot_task"], "press the upper arm")
        self.assertEqual(payload["asset_class"], "articulated")
        self.assertTrue(payload["auto_submit"])
        self.assertEqual(payload["physical_context"], {"mass_kg": 0.3})

    def test_image_submission_uses_repeated_images_array(self):
        client = RecordingClient()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image:
            image.write(b"png")
            image_path = image.name
        try:
            client.create_composition("stapler", "press", images=[image_path])
        finally:
            os.unlink(image_path)
        _method, _path, kwargs = client.calls[0]
        body = kwargs["body"]
        self.assertIn(b'name="images[]"', body)
        self.assertIn(b'name="robot_task"', body)

    def test_composition_wait_links_to_completed_conversion(self):
        client = WorkflowClient()
        composition = Composition(client, {"id": "composition-1", "workflow": {
            "status": "running", "progress": 0}})
        composition.wait(interval=0.001, timeout=1)
        self.assertEqual(composition.status, "completed")
        self.assertEqual(composition.conversion_job_id, "job-1")
        self.assertEqual(composition.conversion_job().status, "completed")

    def test_compose_cli_defaults_to_auto_submit_with_review_opt_out(self):
        parser = build_parser()
        args = parser.parse_args(["compose", "stapler", "--task", "press"])
        self.assertFalse(args.review)
        self.assertEqual(args.asset_class, "auto")
        review = parser.parse_args([
            "compose", "stapler", "--task", "press", "--review",
            "--dimensions", "0.15", "0.04", "0.08",
        ])
        self.assertTrue(review.review)
        self.assertEqual(review.dimensions, [0.15, 0.04, 0.08])


if __name__ == "__main__":
    unittest.main()
