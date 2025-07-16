"""Some code in this file was copied from panel (https://github.com/holoviz/panel) which
is covered by the following LICENSE


Copyright (c) 2018, HoloViz team (holoviz.org).
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

 * Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.

 * Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the
   distribution.

 * Neither the name of the copyright holder nor the names of any
   contributors may be used to endorse or promote products derived
   from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, AnyStr, ClassVar, Optional

import param
from panel.layout import Column, ListPanel
from panel.models.widgets import DoubleClickEvent
from panel.util import fullpath
from panel.viewable import Layoutable
from panel.widgets import MultiSelect
from panel.widgets.file_selector import BaseFileNavigator

if TYPE_CHECKING:
    from fsspec import AbstractFileSystem


class FileBrowser(BaseFileNavigator):
    """File browser widget based on pn.widgets.FileSelector.

    Uses a MultiSelect instead of a CrossSelector to more closely mimick typical OS file
    dialogs.
    """

    show_hidden = param.Boolean(
        default=False,
        doc="Whether to show hidden files and directories (starting with a period).",
    )

    size = param.Integer(default=10, doc="The number of options shown at once.")

    multiselect = param.Boolean(
        default=True, allow_refs=True, doc="Allow selecting multiple files."
    )

    doubleclick = param.Event(doc="Event when the user has double-clicked a file.")

    _composite_type: ClassVar[type[ListPanel]] = Column

    def __init__(
        self,
        directory: AnyStr | os.PathLike | None = None,
        fs: AbstractFileSystem | None = None,
        **params,
    ):
        # Mostly copied from FileSelector
        if params.get("width") and params.get("height") and "sizing_mode" not in params:
            params["sizing_mode"] = None

        layout = {
            p: getattr(self, p)
            for p in Layoutable.param
            if p not in ("name", "height", "margin") and getattr(self, p) is not None
        }
        sel_layout = dict(layout, sizing_mode="stretch_width", height=300, margin=0)
        self._selector = MultiSelect(
            size=self.param.size,
            **dict(sel_layout, visible=self.param.visible),
        )

        super().__init__(directory=directory, fs=fs, **params)

        self._selector.on_double_click(self._select_and_go)
        self._selector.param.watch(self._update_value, "value")

    def _select_and_go(self, event: DoubleClickEvent):
        # Mostly copied from FileSelector, but trigger doubleclick event when
        # double-clicking a file.
        relpath = event.option.replace("📁", "").replace("⬆ ", "")
        if relpath == "..":
            return self._go_up()
        sel = fullpath(os.path.join(self._cwd, relpath))
        if self._provider.isdir(sel):
            self._directory.value = sel
            self._update_files()
        else:
            self.doubleclick = True

    def _update_value(self, event: param.parameterized.Event):
        # Mostly copied from FileSelector, add logic for
        value = [
            v
            for v in event.new
            if v != ".." and (not self.only_files or os.path.isfile(v))
        ]
        if not self.multiselect and len(value) > 1:
            value = [v for v in value if v not in event.old][:1]
        self._selector.value = value
        self.value = value

    def _update_files(
        self,
        event: Optional[param.parameterized.Event] = None,  # noqa: UP007 UP045
        refresh: bool = False,
    ):
        path = self._provider.normalize(self._directory.value)
        super()._update_files(event, refresh)
        selected = self.value
        dirs, files = self._provider.ls(path, self.file_pattern)

        paths = [
            p
            for p in sorted(dirs) + sorted(files)
            if self.show_hidden or not os.path.basename(p).startswith(".")
        ]
        abbreviated = [
            ("📁" if f in dirs else "") + os.path.relpath(f, self.directory)
            for f in paths
        ]
        if not self._up.disabled:
            paths.insert(0, "..")
            abbreviated.insert(0, "⬆ ..")

        options = dict(zip(abbreviated, paths))
        self._selector.options = options
        self._selector.value = [s for s in selected if s in paths]

    def update(self):
        self._update_files()
