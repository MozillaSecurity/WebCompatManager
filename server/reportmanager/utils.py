# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import html
import re


def preprocess_text(text):
    if not text or text == "":
        return ""

    text = html.unescape(text)
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    return text
