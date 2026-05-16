from __future__ import annotations

import os
import tempfile


_original_mkdtemp = tempfile.mkdtemp


def _writable_mkdtemp(suffix=None, prefix=None, dir=None):
    if suffix is None:
        suffix = ""
    if prefix is None:
        prefix = tempfile.template
    if dir is None:
        dir = tempfile.gettempdir()
    for _ in range(tempfile.TMP_MAX):
        name = next(tempfile._get_candidate_names())
        file = os.path.abspath(os.path.join(dir, prefix + name + suffix))
        try:
            os.mkdir(file)
        except FileExistsError:
            continue
        return file
    return _original_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)


tempfile.mkdtemp = _writable_mkdtemp
