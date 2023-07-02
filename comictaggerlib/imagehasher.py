"""A class to manage creating image content hashes, and calculate hamming distances"""
#
# Copyright 2013 ComicTagger Authors
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
from __future__ import annotations

import io
import logging
import math
from functools import reduce
from statistics import median
from typing import TypeVar

try:
    from PIL import Image

    pil_available = True
except ImportError:
    pil_available = False
logger = logging.getLogger(__name__)


class ImageHasher:
    def __init__(self, path: str | None = None, data: bytes = b"", width: int = 8, height: int = 8) -> None:
        self.width = width
        self.height = height

        if path is None and not data:
            raise OSError

        try:
            if path is not None:
                self.image = Image.open(path)
            else:
                self.image = Image.open(io.BytesIO(data))
        except Exception:
            logger.exception("Image data seems corrupted!")
            # just generate a bogus image
            self.image = Image.new("L", (1, 1))

    def average_hash(self) -> int:
        try:
            image = self.image.resize((self.width, self.height), Image.Resampling.LANCZOS).convert("L")
        except Exception:
            logger.exception("average_hash error")
            return 0

        pixels = list(image.getdata())
        avg = sum(pixels) / len(pixels)

        def compare_value_to_avg(i: int) -> int:
            return 1 if i > avg else 0

        bitlist = list(map(compare_value_to_avg, pixels))

        # build up an int value from the bit list, one bit at a time
        def set_bit(x: int, idx_val: tuple[int, int]) -> int:
            (idx, val) = idx_val
            return x | (val << idx)

        result = reduce(set_bit, enumerate(bitlist), 0)

        return result

    def average_hash2(self) -> None:
        """
        # Got this one from somewhere on the net.  Not a clue how the 'convolve2d' works!

        from numpy import array
        from scipy.signal import convolve2d

        im = self.image.resize((self.width, self.height), Image.ANTIALIAS).convert('L')

        in_data = array((im.getdata())).reshape(self.width, self.height)
        filt = array([[0,1,0],[1,-4,1],[0,1,0]])
        filt_data = convolve2d(in_data,filt,mode='same',boundary='symm').flatten()

        result = reduce(lambda x, (y, z): x | (z << y),
                         enumerate(map(lambda i: 0 if i < 0 else 1, filt_data)),
                         0)
        return result
        """

    def p_hash(self) -> int:
        """
        Pure python version of Perceptual Hash computation of https://github.com/JohannesBuchner/imagehash/tree/master
        Implementation follows http://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html
        """

        def generate_dct2(block, axis=0):
            def dct1(block):
                """Perform 1D Discrete Cosine Transform (DCT) on a given block."""
                N = len(block)
                dct_block = [0.0] * N

                for k in range(N):
                    sum_val = 0.0
                    for n in range(N):
                        cos_val = math.cos(math.pi * k * (2 * n + 1) / (2 * N))
                        sum_val += block[n] * cos_val
                    dct_block[k] = sum_val

                return dct_block

            """Perform 2D Discrete Cosine Transform (DCT) on a given block along the specified axis."""
            rows = len(block)
            cols = len(block[0])
            dct_block = [[0.0] * cols for _ in range(rows)]

            if axis == 0:
                # Apply 1D DCT on each row
                for i in range(rows):
                    dct_block[i] = dct1(block[i])
            elif axis == 1:
                # Apply 1D DCT on each column
                for j in range(cols):
                    column = [block[i][j] for i in range(rows)]
                    dct_column = dct1(column)
                    for i in range(rows):
                        dct_block[i][j] = dct_column[i]
            else:
                raise ValueError("Invalid axis value. Must be either 0 or 1.")

            return dct_block

        def convert_image_to_ndarray(image):
            width, height = image.size

            pixels2 = []
            for y in range(height):
                row = []
                for x in range(width):
                    pixel = image.getpixel((x, y))
                    row.append(pixel)
                pixels2.append(row)

            return pixels2

        highfreq_factor = 4
        img_size = 8 * highfreq_factor

        try:
            image = self.image.convert("L").resize((img_size, img_size), Image.Resampling.LANCZOS)
        except Exception:
            logger.exception("p_hash error converting to greyscale and resizing")
            return 0

        pixels = convert_image_to_ndarray(image)
        dct = generate_dct2(generate_dct2(pixels, axis=0), axis=1)
        dctlowfreq = [row[:8] for row in dct[:8]]
        med = median([item for sublist in dctlowfreq for item in sublist])
        # Convert to a bit string
        diff = "".join(str(int(item > med)) for row in dctlowfreq for item in row)

        result = int(diff, 2)

        return result

    # accepts 2 hashes (longs or hex strings) and returns the hamming distance

    T = TypeVar("T", int, str)

    @staticmethod
    def hamming_distance(h1: T, h2: T) -> int:
        if isinstance(h1, int) or isinstance(h2, int):
            n1 = h1
            n2 = h2
        else:
            # convert hex strings to ints
            n1 = int(h1, 16)
            n2 = int(h2, 16)

        # xor the two numbers
        n = n1 ^ n2

        # count up the 1's in the binary string
        return sum(b == "1" for b in bin(n)[2:])
