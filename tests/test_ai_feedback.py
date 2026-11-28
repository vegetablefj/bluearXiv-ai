import json
import os
import unittest
from contextlib import redirect_stdout
from io import BytesIO, TextIOWrapper
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import ai_feedback


def completion(content, finish_reason="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=finish_reason, message=SimpleNamespace(content=content))],
        usage=None,
    )


class TranslationTests(unittest.TestCase):
    def test_retries_truncated_output_with_more_tokens(self):
        client = Mock()
        create = client.chat.completions.create
        create.side_effect = [
            completion("0\n不完整的译文", "length"),
            completion("1\n在假设成立时，我们证明该结论。\n\n我们还给出一个例子。"),
        ]
        messages = [{"role": "user", "content": "an abstract"}]

        selected, translation = ai_feedback.request_translation(client, messages)

        self.assertTrue(selected)
        self.assertEqual(translation, "在假设成立时，我们证明该结论。\n\n我们还给出一个例子。")
        self.assertEqual([call.kwargs["max_tokens"] for call in create.call_args_list], [1024, 2048])
        self.assertTrue(all(call.kwargs["messages"] == messages for call in create.call_args_list))

    def test_rejects_truncated_output_after_one_retry(self):
        client = Mock()
        create = client.chat.completions.create
        create.return_value = completion("1\n虽然格式正确，但这段译文被截断。", "length")

        with self.assertRaisesRegex(RuntimeError, "仍被截断"):
            ai_feedback.request_translation(client, [])

        self.assertEqual(create.call_count, 2)

    def test_invalid_completion_is_rejected_without_retry(self):
        responses = (
            completion(None),
            completion("0\n   "),
            completion("2\n一段译文。"),
            completion("0\n一段译文。", "content_filter"),
            SimpleNamespace(choices=[], usage=None),
        )
        for response in responses:
            with self.subTest(response=response):
                client = Mock()
                create = client.chat.completions.create
                create.return_value = response

                with self.assertRaises(RuntimeError):
                    ai_feedback.request_translation(client, [])

                create.assert_called_once()

    def test_keeps_paper_without_abstract_and_translates_the_next_paper(self):
        papers = [
            {"id": "2611.00001", "title": "Missing", "abstract": "   "},
            {"id": "2611.00002", "title": "Present 🧮", "abstract": "We give evidence for the conjecture."},
        ]
        with TemporaryDirectory() as temporary:
            raw = Path(temporary)
            (raw / "all_papers_unique.json").write_text(json.dumps(papers), encoding="utf-8")
            options = {"BLUEARXIV_DATA_RAW_DIR": temporary, "DEEPSEEK_API_KEY": "test-key"}
            with patch.dict(os.environ, options), patch.object(ai_feedback, "OpenAI") as create_client:
                create = create_client.return_value.chat.completions.create
                create.return_value = completion("1\n我们为该猜想提供证据。 🧮")

                console = BytesIO()
                with TextIOWrapper(console, encoding="gbk", errors="strict") as stdout:
                    with redirect_stdout(stdout):
                        result, selected_count = ai_feedback.process_all_papers()
                    stdout.flush()
                    log = console.getvalue().decode("gbk")

                create.assert_called_once()
                messages = create.call_args.kwargs["messages"]
                user_data = json.loads(messages[1]["content"].split("\n", 1)[1])
                self.assertEqual(user_data["abstract"], papers[1]["abstract"])
                self.assertEqual(user_data["title"], papers[1]["title"])
            saved = json.loads((raw / "all_papers_feedback.json").read_text(encoding="utf-8"))

        self.assertIn("普通论文", log)
        self.assertIn("精选论文", log)
        self.assertIn(r"Present \U0001f9ee", log)
        self.assertEqual(saved, result)
        self.assertFalse(result[0]["selected"])
        self.assertEqual(result[0]["comment"], ai_feedback.MISSING_ABSTRACT)
        self.assertEqual(result[1]["comment"], "我们为该猜想提供证据。 🧮")
        self.assertEqual(selected_count, 1)


if __name__ == "__main__":
    unittest.main()
