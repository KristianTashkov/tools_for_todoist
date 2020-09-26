"""
Copyright (C) 2020-2020 Kristian Tashkov <kristian.tashkov@gmail.com>

This file is part of Todoist Helper.

Todoist Helper is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Todoist Helper is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
more details.

You should have received a copy of the GNU General Public License along
with this program. If not, see <http://www.gnu.org/licenses/>.
"""

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="Todoist Helper",
    version="0.0.1",
    author="Kristian Tashkov",
    author_email="kristian.tashkov@gmail.com",
    description="Todoist helper functions",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/KristianTashkov/todoist_helper",
    packages=setuptools.find_packages(),
    python_requires='>=3.7',
)
