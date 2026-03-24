# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import html
import re


def preprocess_text(text: str | None) -> str:
    if not text or text == "":
        return ""

    text = html.unescape(text)
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def transform_ml_label(
    ml_label: str | None, ml_probability: float | None
) -> float | None:
    """Transform ML label and probability into a valid probability.

    The BugBot ML prediction can assign two labels, "invalid" or "valid",
    with a probability between 0 and 1. Having two labels makes filtering
    and sorting harder, so we transform "invalid 95%" into "valid 5%".

    There is a chance that a bug will have no label and score. In this case,
    we just assign None, which will get treated as invalid in the
    frontend.

    Args:
        ml_label: The ML label ("invalid" or "valid"), or None if missing
        ml_probability: The probability value (0-1), or None if missing

    Returns:
        The probability that the report is valid, or None if label is unknown
    """
    ml_valid_probability: float | None = None
    match ml_label:
        case "invalid":
            ml_valid_probability = (
                1 - ml_probability if ml_probability is not None else None
            )
        case "valid":
            ml_valid_probability = ml_probability
    return ml_valid_probability
