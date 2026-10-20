"""库：可复用的常识。导入即登记（渲染与规则各登记一次）。"""

from __future__ import annotations

from . import concepts as _concepts  # noqa: F401  规则在导入时登记
from . import institutions as _institutions  # noqa: F401
from . import renderers as _renderers  # noqa: F401  状态渲染在导入时登记
from .institutions import EFFECTS  # noqa: F401

__all__ = ["EFFECTS"]
