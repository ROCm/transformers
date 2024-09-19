# Copyright 2024 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import shutil
import tempfile
import unittest

import requests
import torch

from transformers.testing_utils import (
    require_torch,
    require_vision,
)
from transformers.utils import is_vision_available

from ...test_processing_common import ProcessorTesterMixin


if is_vision_available():
    from PIL import Image

    from transformers import AutoTokenizer, PixtralImageProcessor, PixtralProcessor


@require_vision
class PixtralProcessorTest(ProcessorTesterMixin, unittest.TestCase):
    processor_class = PixtralProcessor

    @classmethod
    def setUpClass(cls):
        cls.url_0 = "https://www.ilankelman.org/stopsigns/australia.jpg"
        cls.image_0 = Image.open(requests.get(cls.url_0, stream=True).raw)
        cls.url_1 = "http://images.cocodataset.org/val2017/000000039769.jpg"
        cls.image_1 = Image.open(requests.get(cls.url_1, stream=True).raw)
        cls.url_2 = "https://huggingface.co/microsoft/kosmos-2-patch14-224/resolve/main/snowman.jpg"
        cls.image_2 = Image.open(requests.get(cls.url_2, stream=True).raw)

    def setUp(self):
        self.tmpdirname = tempfile.mkdtemp()

        # FIXME - just load the processor directly from the checkpoint
        tokenizer = AutoTokenizer.from_pretrained("hf-internal-testing/pixtral-12b")
        image_processor = PixtralImageProcessor()
        processor = PixtralProcessor(tokenizer=tokenizer, image_processor=image_processor)
        processor.save_pretrained(self.tmpdirname)

    def tearDown(self):
        shutil.rmtree(self.tmpdirname)

    @unittest.skip("No chat template was set for this model (yet)")
    def test_chat_template(self):
        processor = self.processor_class.from_pretrained(self.tmpdirname)
        expected_prompt = "USER: [IMG]\nWhat is shown in this image? ASSISTANT:"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": "What is shown in this image?"},
                ],
            },
        ]
        formatted_prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
        self.assertEqual(expected_prompt, formatted_prompt)

    @unittest.skip("No chat template was set for this model (yet)")
    def test_image_token_filling(self):
        processor = self.processor_class.from_pretrained(self.tmpdirname)
        # Important to check with non square image
        image = torch.randint(0, 2, (3, 500, 316))
        expected_image_tokens = 1526
        image_token_index = 32000

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": "What is shown in this image?"},
                ],
            },
        ]
        inputs = processor(
            text=[processor.apply_chat_template(messages)],
            images=[image],
            return_tensors="pt",
        )
        image_tokens = (inputs["input_ids"] == image_token_index).sum().item()
        self.assertEqual(expected_image_tokens, image_tokens)

    def test_processor_with_single_image(self):
        processor = self.processor_class.from_pretrained(self.tmpdirname)
        prompt_string = "USER: [IMG]\nWhat's the content of the image? ASSISTANT:"

        # Make small for checking image token expansion
        processor.image_processor.size = {"longest_edge": 30}
        processor.image_processor.patch_size = {"height": 2, "width": 2}

        # Test passing in an image
        inputs_image = processor(text=prompt_string, images=self.image_0, return_tensors="pt")
        self.assertIn("input_ids", inputs_image)
        self.assertTrue(len(inputs_image["input_ids"]) == 1)
        self.assertIsInstance(inputs_image["input_ids"], torch.Tensor)
        self.assertIsInstance(inputs_image["pixel_values"], list)
        self.assertTrue(len(inputs_image["pixel_values"]) == 1)
        self.assertIsInstance(inputs_image["pixel_values"][0], list)
        self.assertTrue(len(inputs_image["pixel_values"][0]) == 1)
        self.assertIsInstance(inputs_image["pixel_values"][0][0], torch.Tensor)

        # fmt: off
        input_ids = inputs_image["input_ids"]
        self.assertEqual(
            input_ids[0].tolist(),
            # Equivalent to "USER: [IMG][IMG][IMG_BREAK][IMG][IMG][IMG_END]\nWhat's the content of the image? ASSISTANT:"
            [21510,  1058,  1032,    10,    10,    12,    10,    10,    13,  1010, 7493,  1681,  1278,  4701,  1307,  1278,  3937,  1063,  1349,  4290, 16002, 41150,  1058]
        )
        # fmt: on

        # Test passing in a url
        inputs_url = processor(text=prompt_string, images=self.url_0, return_tensors="pt")
        self.assertIn("input_ids", inputs_url)
        self.assertTrue(len(inputs_url["input_ids"]) == 1)
        self.assertIsInstance(inputs_url["input_ids"], torch.Tensor)
        self.assertIsInstance(inputs_url["pixel_values"], list)
        self.assertTrue(len(inputs_url["pixel_values"]) == 1)
        self.assertIsInstance(inputs_url["pixel_values"][0], list)
        self.assertTrue(len(inputs_url["pixel_values"][0]) == 1)
        self.assertIsInstance(inputs_url["pixel_values"][0][0], torch.Tensor)

        # fmt: off
        input_ids = inputs_url["input_ids"]
        self.assertEqual(
            input_ids[0].tolist(),
            # Equivalent to "USER: [IMG][IMG][IMG_BREAK][IMG][IMG][IMG_END]\nWhat's the content of the image? ASSISTANT:"
            [21510,  1058,  1032,    10,    10,    12,    10,    10,    13,  1010, 7493,  1681,  1278,  4701,  1307,  1278,  3937,  1063,  1349,  4290, 16002, 41150,  1058]
        )
        # fmt: on

    def test_processor_with_multiple_images_single_list(self):
        processor = self.processor_class.from_pretrained(self.tmpdirname)
        prompt_string = "USER: [IMG][IMG]\nWhat's the difference between these two images? ASSISTANT:"

        # Make small for checking image token expansion
        processor.image_processor.size = {"longest_edge": 30}
        processor.image_processor.patch_size = {"height": 2, "width": 2}

        # Test passing in an image
        inputs_image = processor(text=prompt_string, images=[self.image_0, self.image_1], return_tensors="pt")
        self.assertIn("input_ids", inputs_image)
        self.assertTrue(len(inputs_image["input_ids"]) == 1)
        self.assertIsInstance(inputs_image["input_ids"], torch.Tensor)
        self.assertIsInstance(inputs_image["pixel_values"], list)
        self.assertTrue(len(inputs_image["pixel_values"]) == 1)
        self.assertIsInstance(inputs_image["pixel_values"][0], list)
        self.assertTrue(len(inputs_image["pixel_values"][0]) == 2)
        self.assertIsInstance(inputs_image["pixel_values"][0][0], torch.Tensor)

        # fmt: off
        input_ids = inputs_image["input_ids"]
        self.assertEqual(
            input_ids[0].tolist(),
            # Equivalent to ["USER: [IMG][IMG][IMG_BREAK][IMG][IMG][IMG_END][IMG][IMG][IMG_BREAK][IMG][IMG][IMG_END]\nWhat's the difference between these two images? ASSISTANT:"]
            [21510, 1058, 1032, 10, 10, 12, 10, 10, 13, 10, 10, 12, 10, 10, 13, 1010, 7493, 1681, 1278, 6592, 2396, 2576, 2295, 8061, 1063, 1349, 4290, 16002, 41150, 1058]
        )
        # fmt: on

        # Test passing in a url
        inputs_url = processor(text=prompt_string, images=[self.url_0, self.url_1], return_tensors="pt")
        self.assertIn("input_ids", inputs_url)
        self.assertTrue(len(inputs_url["input_ids"]) == 1)
        self.assertIsInstance(inputs_url["input_ids"], torch.Tensor)
        self.assertIsInstance(inputs_url["pixel_values"], list)
        self.assertTrue(len(inputs_url["pixel_values"]) == 1)
        self.assertIsInstance(inputs_url["pixel_values"][0], list)
        self.assertTrue(len(inputs_url["pixel_values"][0]) == 2)
        self.assertIsInstance(inputs_url["pixel_values"][0][0], torch.Tensor)
        # fmt: off
        input_ids = inputs_url["input_ids"]
        self.assertEqual(
            input_ids[0].tolist(),
            # Equivalent to ["USER: [IMG][IMG][IMG_BREAK][IMG][IMG][IMG_END][IMG][IMG][IMG_BREAK][IMG][IMG][IMG_END]\nWhat's the difference between these two images? ASSISTANT:"]
            [21510, 1058, 1032, 10, 10, 12, 10, 10, 13, 10, 10, 12, 10, 10, 13, 1010, 7493, 1681, 1278, 6592, 2396, 2576, 2295, 8061, 1063, 1349, 4290, 16002, 41150, 1058]
        )
        # fmt: on

    def test_processor_with_multiple_images_multiple_lists(self):
        processor = self.processor_class.from_pretrained(self.tmpdirname)
        prompt_string = [
            "USER: [IMG][IMG]\nWhat's the difference between these two images? ASSISTANT:",
            "USER: [IMG]\nWhat's the content of the image? ASSISTANT:",
        ]
        processor.tokenizer.pad_token = "</s>"
        image_inputs = [[self.image_0, self.image_1], [self.image_2]]

        # Make small for checking image token expansion
        processor.image_processor.size = {"longest_edge": 30}
        processor.image_processor.patch_size = {"height": 2, "width": 2}

        # Test passing in an image
        inputs_image = processor(text=prompt_string, images=image_inputs, return_tensors="pt", padding=True)
        self.assertIn("input_ids", inputs_image)
        self.assertTrue(len(inputs_image["input_ids"]) == 2)
        self.assertIsInstance(inputs_image["input_ids"], torch.Tensor)
        self.assertIsInstance(inputs_image["pixel_values"], list)
        self.assertTrue(len(inputs_image["pixel_values"]) == 2)
        self.assertIsInstance(inputs_image["pixel_values"][0], list)
        self.assertTrue(len(inputs_image["pixel_values"][0]) == 2)
        self.assertIsInstance(inputs_image["pixel_values"][0][0], torch.Tensor)

        # fmt: off
        input_ids = inputs_image["input_ids"]
        self.assertEqual(
            input_ids[0].tolist(),
            # Equivalent to ["USER: [IMG][IMG][IMG_BREAK][IMG][IMG][IMG_END][IMG][IMG][IMG_BREAK][IMG][IMG][IMG_END]\nWhat's the difference between these two images? ASSISTANT:"]
            [21510, 1058, 1032, 10, 10, 12, 10, 10, 13, 10, 10, 12, 10, 10, 13, 1010, 7493, 1681, 1278, 6592, 2396, 2576, 2295, 8061, 1063, 1349, 4290, 16002, 41150, 1058]
        )
        # fmt: on

        # Test passing in a url
        inputs_url = processor(text=prompt_string, images=image_inputs, return_tensors="pt", padding=True)
        self.assertIn("input_ids", inputs_url)
        self.assertTrue(len(inputs_url["input_ids"]) == 2)
        self.assertIsInstance(inputs_url["input_ids"], torch.Tensor)
        self.assertIsInstance(inputs_url["pixel_values"], list)
        self.assertTrue(len(inputs_url["pixel_values"]) == 2)
        self.assertIsInstance(inputs_url["pixel_values"][0], list)
        self.assertTrue(len(inputs_url["pixel_values"][0]) == 2)
        self.assertIsInstance(inputs_url["pixel_values"][0][0], torch.Tensor)

        # fmt: off
        input_ids = inputs_url["input_ids"]
        self.assertEqual(
            input_ids[0].tolist(),
            # Equivalent to ["USER: [IMG][IMG][IMG_BREAK][IMG][IMG][IMG_END][IMG][IMG][IMG_BREAK][IMG][IMG][IMG_END]\nWhat's the difference between these two images? ASSISTANT:"]
            [21510, 1058, 1032, 10, 10, 12, 10, 10, 13, 10, 10, 12, 10, 10, 13, 1010, 7493, 1681, 1278, 6592, 2396, 2576, 2295, 8061, 1063, 1349, 4290, 16002, 41150, 1058]
        )
        # fmt: on

    # Override all tests requiring shape as returning tensor batches is not supported by PixtralProcessor

    @require_torch
    @require_vision
    def test_image_processor_defaults_preserved_by_image_kwargs(self):
        if "image_processor" not in self.processor_class.attributes:
            self.skipTest(f"image_processor attribute not present in {self.processor_class}")
        image_processor = self.get_component("image_processor", size={"height": 240, "width": 240})
        tokenizer = self.get_component("tokenizer", max_length=117, padding="max_length")

        processor = self.processor_class(tokenizer=tokenizer, image_processor=image_processor)
        self.skip_processor_without_typed_kwargs(processor)

        input_str = "lower newer"
        image_input = self.prepare_image_inputs()

        inputs = processor(text=input_str, images=image_input)
        # Added dimension by pixtral image processor
        self.assertEqual(len(inputs["pixel_values"][0][0][0][0]), 240)

    @require_torch
    @require_vision
    def test_kwargs_overrides_default_image_processor_kwargs(self):
        if "image_processor" not in self.processor_class.attributes:
            self.skipTest(f"image_processor attribute not present in {self.processor_class}")
        image_processor = self.get_component("image_processor", size={"height": 400, "width": 400})
        tokenizer = self.get_component("tokenizer", max_length=117, padding="max_length")

        processor = self.processor_class(tokenizer=tokenizer, image_processor=image_processor)
        self.skip_processor_without_typed_kwargs(processor)

        input_str = "lower newer"
        image_input = self.prepare_image_inputs()

        inputs = processor(text=input_str, images=image_input, size={"height": 240, "width": 240})
        self.assertEqual(len(inputs["pixel_values"][0][0][0][0]), 240)

    @require_torch
    @require_vision
    def test_structured_kwargs_nested(self):
        if "image_processor" not in self.processor_class.attributes:
            self.skipTest(f"image_processor attribute not present in {self.processor_class}")
        image_processor = self.get_component("image_processor")
        tokenizer = self.get_component("tokenizer")

        processor = self.processor_class(tokenizer=tokenizer, image_processor=image_processor)
        self.skip_processor_without_typed_kwargs(processor)

        input_str = "lower newer"
        image_input = self.prepare_image_inputs()

        # Define the kwargs for each modality
        all_kwargs = {
            "common_kwargs": {"return_tensors": "pt"},
            "images_kwargs": {"size": {"height": 240, "width": 240}},
            "text_kwargs": {"padding": "max_length", "max_length": 76},
        }

        inputs = processor(text=input_str, images=image_input, **all_kwargs)
        self.skip_processor_without_typed_kwargs(processor)

        self.assertEqual(inputs["pixel_values"][0][0].shape[-1], 240)

        self.assertEqual(len(inputs["input_ids"][0]), 76)

    @require_torch
    @require_vision
    def test_structured_kwargs_nested_from_dict(self):
        if "image_processor" not in self.processor_class.attributes:
            self.skipTest(f"image_processor attribute not present in {self.processor_class}")

        image_processor = self.get_component("image_processor")
        tokenizer = self.get_component("tokenizer")

        processor = self.processor_class(tokenizer=tokenizer, image_processor=image_processor)
        self.skip_processor_without_typed_kwargs(processor)
        input_str = "lower newer"
        image_input = self.prepare_image_inputs()

        # Define the kwargs for each modality
        all_kwargs = {
            "common_kwargs": {"return_tensors": "pt"},
            "images_kwargs": {"size": {"height": 240, "width": 240}},
            "text_kwargs": {"padding": "max_length", "max_length": 76},
        }

        inputs = processor(text=input_str, images=image_input, **all_kwargs)
        self.assertEqual(inputs["pixel_values"][0][0].shape[-1], 240)

        self.assertEqual(len(inputs["input_ids"][0]), 76)

    @require_torch
    @require_vision
    def test_unstructured_kwargs(self):
        if "image_processor" not in self.processor_class.attributes:
            self.skipTest(f"image_processor attribute not present in {self.processor_class}")
        image_processor = self.get_component("image_processor")
        tokenizer = self.get_component("tokenizer")

        processor = self.processor_class(tokenizer=tokenizer, image_processor=image_processor)
        self.skip_processor_without_typed_kwargs(processor)

        input_str = "lower newer"
        image_input = self.prepare_image_inputs()
        inputs = processor(
            text=input_str,
            images=image_input,
            return_tensors="pt",
            size={"height": 240, "width": 240},
            padding="max_length",
            max_length=76,
        )

        self.assertEqual(inputs["pixel_values"][0][0].shape[-1], 240)
        self.assertEqual(len(inputs["input_ids"][0]), 76)

    @require_torch
    @require_vision
    def test_unstructured_kwargs_batched(self):
        if "image_processor" not in self.processor_class.attributes:
            self.skipTest(f"image_processor attribute not present in {self.processor_class}")
        image_processor = self.get_component("image_processor")
        tokenizer = self.get_component("tokenizer")

        processor = self.processor_class(tokenizer=tokenizer, image_processor=image_processor)
        self.skip_processor_without_typed_kwargs(processor)

        input_str = ["lower newer", "upper older longer string"]
        # images needs to be nested to detect multiple prompts
        image_input = [self.prepare_image_inputs()] * 2
        inputs = processor(
            text=input_str,
            images=image_input,
            return_tensors="pt",
            size={"height": 240, "width": 240},
            padding="longest",
            max_length=76,
        )

        self.assertEqual(inputs["pixel_values"][0][0].shape[-1], 240)
        self.assertEqual(len(inputs["input_ids"][0]), 4)
