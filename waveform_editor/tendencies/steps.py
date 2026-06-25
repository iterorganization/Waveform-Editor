import numpy as np

from waveform_editor.tendencies.piecewise import PiecewiseLinearTendency


class StepsTendency(PiecewiseLinearTendency):
    """A piecewise-constant (zero-order-hold) tendency.

    Each ``time`` is the start of a step holding the corresponding ``value`` until the
    next breakpoint; the final value is held until the tendency's ``end``. Unlike the
    piecewise-linear tendency, the values are never interpolated, so they may be
    non-numeric (e.g. strings or booleans).

    The start is inferred from the first breakpoint. An explicit ``end`` (or
    ``duration``) may be given so the final value is held for a real duration; if
    neither is given, the tendency ends at the last breakpoint.
    """

    @property
    def is_categorical(self):
        # Strings ("U"/"S"), objects ("O") and booleans ("b") are non-numeric and are
        # held as a step rather than interpolated.
        return self.value.dtype.kind in ("U", "S", "O", "b")

    def _coerce_value(self, value):
        # A step function is never interpolated, so keep the native dtype (which may be
        # non-numeric) instead of coercing to float like the piecewise-linear tendency.
        return np.asarray(value)

    def _resolve_time_bounds(self, time, kwargs):
        # The start is fixed at the first breakpoint, but (unlike piecewise-linear) an
        # explicit end/duration is allowed so the final value can be held for a real
        # duration. Without one, the tendency ends at the last breakpoint.
        line_number = kwargs.get("line_number", 0)
        if "user_start" in kwargs:
            kwargs.pop("user_start")
            self.pre_check_annotations.add(
                line_number, "'start' is not allowed in a steps tendency\n"
            )
        end = kwargs.get("user_end")
        if end is None and kwargs.get("user_duration") is None:
            kwargs["user_end"] = time[-1]
        elif isinstance(end, (int, float)) and end < time[-1]:
            self.pre_check_annotations.add(
                line_number,
                "The `end` of a steps tendency must not precede the last time.\n",
            )
        return {"user_start": time[0]}

    def get_value(self, time: np.ndarray | None = None):
        if time is None:
            return self.time, self.value
        indices = np.searchsorted(self.time, time, side="right") - 1
        indices = np.clip(indices, 0, len(self.value) - 1)
        return time, self.value[indices]

    def get_derivative(self, time: np.ndarray) -> np.ndarray:
        return np.zeros_like(time, dtype=float)
