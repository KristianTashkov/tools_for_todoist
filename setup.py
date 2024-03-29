"""
Copyright (C) 2020-2020 Kristian Tashkov <kristian.tashkov@gmail.com>

This file is part of "Tools for Todoist".

"Tools for Todoist" is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

"Tools for Todoist" is distributed in the hope that it will be useful, but
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
    name="Tools for Todoist",
    version="0.0.1",
    author="Kristian Tashkov",
    author_email="kristian.tashkov@gmail.com",
    description="Tools for todoist",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/KristianTashkov/tools_for_todoist",
    packages=setuptools.find_packages(),
    python_requires='>=3.9',
    install_requires=[
        'todoist-python==8.1.4',
        'google-api-python-client==1.12.2',
        'google-auth-httplib2==0.0.4',
        'google-auth-oauthlib==0.4.1',
        'google-cloud-logging==3.6.0',
        'python-dateutil==2.8.1',
        'psycopg2-binary==2.9.7',
        'markdownify==0.11.6',
    ],
    extras_require={'test': ['flake8==6.1.0', 'pytest==7.4.1', 'isort==5.12.0', 'black==23.7.0']},
    entry_points={
        'console_scripts': [
            'tft_lint=run_lint:main',
        ]
    },
)
