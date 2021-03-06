# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2015-2017 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os
import shutil

from testtools.matchers import Contains, Equals, DirExists, FileExists, Not

from snapcraft.internal import pluginhandler
from snapcraft.internal import project_loader
from . import CommandBaseTestCase


class CleanCommandTestCase(CommandBaseTestCase):

    yaml_template = """name: clean-test
version: 1.0
summary: test clean
description: if the clean is succesful the state file will be updated
icon: icon.png
confinement: strict
grade: stable

parts:
{parts}"""

    yaml_part = """  clean{:d}:
    plugin: nil"""

    def make_snapcraft_yaml(self, n=1, create=True):
        parts = '\n'.join([self.yaml_part.format(i) for i in range(n)])
        super().make_snapcraft_yaml(self.yaml_template.format(parts=parts))
        open('icon.png', 'w').close()

        parts = []
        validator = project_loader.Validator()
        for i in range(n):
            part_name = 'clean{}'.format(i)
            handler = pluginhandler.load_plugin(
                part_name, plugin_name='nil',
                part_properties={'plugin': 'nil'},
                part_schema=validator.part_schema,
                definitions_schema=validator.definitions_schema)
            parts.append({
                'part_dir': handler.code.partdir,
            })

            if create:
                handler.makedirs()
                open(os.path.join(
                    handler.code.installdir, part_name), 'w').close()

                handler.mark_done('pull')
                handler.mark_done('build')

                handler.stage()
                handler.prime()

        return parts

    def test_part_to_remove_not_defined_exits_with_error(self):
        self.make_snapcraft_yaml(n=3)

        result = self.run_command(['clean', 'no-clean'])

        self.assertThat(result.exit_code, Equals(1))
        self.assertThat(result.output, Equals(
            "The part named 'no-clean' is not defined in "
            "'snap/snapcraft.yaml'\n"))

    def test_clean_all(self):
        self.make_snapcraft_yaml(n=3)

        result = self.run_command(['clean'])

        self.assertThat(result.exit_code, Equals(0))
        self.assertThat(self.parts_dir, Not(DirExists()))
        self.assertThat(self.stage_dir, Not(DirExists()))
        self.assertThat(self.prime_dir, Not(DirExists()))

    def test_local_plugin_not_removed(self):
        self.make_snapcraft_yaml(n=3)

        local_plugin = os.path.join(self.local_plugins_dir, 'foo.py')
        os.makedirs(os.path.dirname(local_plugin))
        open(local_plugin, 'w').close()

        result = self.run_command(['clean'])

        self.assertThat(result.exit_code, Equals(0))

        self.assertThat(self.parts_dir, Not(DirExists()))
        self.assertThat(self.stage_dir, Not(DirExists()))
        self.assertThat(self.prime_dir, Not(DirExists()))
        self.assertThat(local_plugin, FileExists())

    def test_clean_all_when_all_parts_specified(self):
        self.make_snapcraft_yaml(n=3)

        result = self.run_command(['clean', 'clean0', 'clean1', 'clean2'])

        self.assertThat(result.exit_code, Equals(0))
        self.assertThat(self.parts_dir, Not(DirExists()))
        self.assertThat(self.stage_dir, Not(DirExists()))
        self.assertThat(self.prime_dir, Not(DirExists()))

    def test_partial_clean(self):
        parts = self.make_snapcraft_yaml(n=3)

        result = self.run_command(['clean', 'clean0', 'clean2'])

        self.assertThat(result.exit_code, Equals(0))
        self.assertThat(self.parts_dir, DirExists())
        self.assertThat(self.stage_dir, DirExists())
        self.assertThat(self.prime_dir, DirExists())

        for i in [0, 2]:
            self.assertThat(parts[i]['part_dir'], Not(DirExists()))

        # Now clean it the rest of the way
        result = self.run_command(['clean', 'clean1'])

        self.assertThat(result.exit_code, Equals(0))
        self.assertThat(self.parts_dir, Not(DirExists()))
        self.assertThat(self.stage_dir, Not(DirExists()))
        self.assertThat(self.prime_dir, Not(DirExists()))

    def test_everything_is_clean(self):
        """Don't crash if everything is already clean."""
        self.make_snapcraft_yaml(n=3, create=False)

        result = self.run_command(['clean'])

        self.assertThat(result.exit_code, Equals(0))

    def test_cleaning_with_strip_does_prime_and_warns(self):
        self.make_snapcraft_yaml(n=3)

        result = self.run_command(['clean', '--step=strip'])

        self.assertThat(result.exit_code, Equals(0))
        self.assertThat(result.output, Contains(
            'DEPRECATED: Use `prime` instead of `strip` as the step to clean'))
        self.assertThat(self.prime_dir, Not(DirExists()))


class CleanCommandReverseDependenciesTestCase(CommandBaseTestCase):

    def setUp(self):
        super().setUp()

        self.make_snapcraft_yaml("""name: clean-test
version: 1.0
summary: test clean
description: test clean
confinement: strict
grade: stable

parts:
  main:
    plugin: nil

  dependent:
    plugin: nil
    after: [main]

  nested-dependent:
    plugin: nil
    after: [dependent]""")

        self.part_dirs = {}
        for part in ['main', 'dependent', 'nested-dependent']:
            self.part_dirs[part] = os.path.join(self.parts_dir, part)
            os.makedirs(os.path.join(self.part_dirs[part], 'state'))
            open(os.path.join(self.part_dirs[part], 'state', 'pull'),
                 'w').close()

        os.makedirs(self.stage_dir)
        os.makedirs(self.prime_dir)

    def assert_clean(self, parts):
        for part in parts:
            self.assertThat(self.part_dirs[part], Not(DirExists()))

    def test_clean_dependent_parts(self):
        result = self.run_command(['clean', 'dependent', 'nested-dependent'])

        self.assertThat(result.exit_code, Equals(0))
        self.assert_clean(['dependent', 'nested-dependent'])
        self.assertThat(self.part_dirs['main'], DirExists())

    def test_clean_part_with_clean_dependent(self):
        result = self.run_command(['clean', 'nested-dependent'])

        self.assertThat(result.exit_code, Equals(0))
        self.assert_clean(['nested-dependent'])

        # Not specifying nested-dependent here should be okay since it's
        # already clean.
        result = self.run_command(['clean', 'dependent'])

        self.assertThat(result.exit_code, Equals(0))
        self.assert_clean(['dependent', 'nested-dependent'])

    def test_clean_part_unspecified_uncleaned_dependent_raises(self):
        # Not specifying nested-dependent here should result in clean raising
        # an exception, saying that it has dependents.
        result = self.run_command(['clean', 'dependent'])

        self.assertThat(result.exit_code, Equals(1))
        self.assertThat(result.output, Equals(
            "Requested clean of 'dependent' but 'nested-dependent' depends "
            "upon it. Please add each to the clean command if that's what you "
            "intended.\n"))

    def test_clean_nested_dependent_parts(self):
        result = self.run_command([
            'clean', 'main', 'dependent', 'nested-dependent'])

        self.assertThat(result.exit_code, Equals(0))
        self.assert_clean(['main', 'dependent', 'nested-dependent'])

    def test_clean_part_with_clean_dependent_uncleaned_nested_dependent(self):
        shutil.rmtree(self.part_dirs['dependent'])
        self.assert_clean(['dependent'])

        # Not specifying dependent here should be okay since it's already
        # clean.
        result = self.run_command(['clean', 'main', 'nested-dependent'])

        self.assertThat(result.exit_code, Equals(0))
        self.assert_clean(['main', 'dependent', 'nested-dependent'])

    def test_clean_part_with_clean_nested_dependent(self):
        shutil.rmtree(self.part_dirs['nested-dependent'])
        self.assert_clean(['nested-dependent'])

        # Not specifying nested-dependent here should be okay since it's
        # already clean.
        result = self.run_command(['clean', 'main', 'dependent'])

        self.assertThat(result.exit_code, Equals(0))
        self.assert_clean(['main', 'dependent', 'nested-dependent'])

    def test_clean_part_unspecified_uncleaned_dependent_with_nest_raises(self):
        # Not specifying dependent here should result in clean raising
        # an exception, saying that it has dependents.
        result = self.run_command(['clean', 'main'])

        self.assertThat(result.exit_code, Equals(1))
        self.assertThat(result.output, Equals(
            "Requested clean of 'main' but 'dependent' depends upon it. "
            "Please add each to the clean command if that's what you "
            "intended.\n"))

    def test_clean_part_unspecified_uncleaned_nested_dependent_raises(self):
        # Not specifying nested-dependent here should result in clean raising
        # an exception, saying that it has dependents.
        result = self.run_command(['clean', 'main', 'dependent'])

        self.assertThat(result.exit_code, Equals(1))
        self.assertThat(result.output, Equals(
            "Requested clean of 'dependent' but 'nested-dependent' depends "
            "upon it. Please add each to the clean command if that's what you "
            "intended.\n"))
