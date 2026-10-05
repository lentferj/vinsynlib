# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026  vinsynlib contributors
#
# This file is part of vinsynlib.
#
# The legend widget needs Textual, which not every user of this library
# does. Nothing here is imported eagerly, so `import vinsynlib.ui` works
# without it and only `vinsynlib.ui.hints` needs the extra.
#
# vinsynlib is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option)
# any later version.
#
# vinsynlib is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.

"""Shared widgets for the terminal front ends.

Import a module, not this package: :mod:`vinsynlib.ui.hints` is the legend,
and it is the only one here so far.
"""
