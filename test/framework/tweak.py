##
# Copyright 2014-2018 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# https://github.com/easybuilders/easybuild
#
# EasyBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EasyBuild.  If not, see <http://www.gnu.org/licenses/>.
##
"""
Unit tests for framework/easyconfig/tweak.py

@author: Kenneth Hoste (Ghent University)
"""
import os
import sys
from test.framework.utilities import EnhancedTestCase, TestLoaderFiltered, init_config
from unittest import TextTestRunner

from easybuild.framework.easyconfig.easyconfig import get_toolchain_hierarchy
from easybuild.framework.easyconfig.parser import EasyConfigParser
from easybuild.framework.easyconfig.tweak import find_matching_easyconfigs, obtain_ec_for, pick_version, tweak_one
from easybuild.framework.easyconfig.tweak import compare_toolchain_specs, match_minimum_tc_specs
from easybuild.framework.easyconfig.tweak import map_toolchain_hierarchies, map_easyconfig_to_target_tc_hierarchy
from easybuild.tools.build_log import EasyBuildError
from easybuild.tools.config import module_classes
from easybuild.tools.filetools import write_file


class TweakTest(EnhancedTestCase):
    """Tests for tweak functionality."""
    def test_pick_version(self):
        """Test pick_version function."""
        # if required version is not available, the most recent version less than or equal should be returned
        self.assertEqual(('1.4', '1.0'), pick_version('1.4', ['0.5', '1.0', '1.5']))

        # if required version is available, that should be what's returned
        self.assertEqual(('1.0', '1.0'), pick_version('1.0', ['0.5', '1.0', '1.5']))

    def test_find_matching_easyconfigs(self):
        """Test find_matching_easyconfigs function."""
        test_easyconfigs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'easyconfigs', 'test_ecs')
        for (name, installver) in [('GCC', '4.8.2'), ('gzip', '1.5-goolf-1.4.10')]:
            ecs = find_matching_easyconfigs(name, installver, [test_easyconfigs_path])
            self.assertTrue(len(ecs) == 1 and ecs[0].endswith('/%s-%s.eb' % (name, installver)))

        ecs = find_matching_easyconfigs('GCC', '*', [test_easyconfigs_path])
        gccvers = ['4.6.3', '4.6.4', '4.7.2', '4.8.2', '4.8.3', '4.9.2', '4.9.3-2.25']
        self.assertEqual(len(ecs), len(gccvers))
        ecs_basename = [os.path.basename(ec) for ec in ecs]
        for gccver in gccvers:
            gcc_ec = 'GCC-%s.eb' % gccver
            self.assertTrue(gcc_ec in ecs_basename, "%s is included in %s" % (gcc_ec, ecs_basename))

    def test_obtain_ec_for(self):
        """Test obtain_ec_for function."""
        test_easyconfigs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'easyconfigs', 'test_ecs')
        # find existing easyconfigs
        specs = {
            'name': 'GCC',
            'version': '4.6.4',
        }
        (generated, ec_file) = obtain_ec_for(specs, [test_easyconfigs_path])
        self.assertFalse(generated)
        self.assertEqual(os.path.basename(ec_file), 'GCC-4.6.4.eb')

        specs = {
            'name': 'ScaLAPACK',
            'version': '2.0.2',
            'toolchain_name': 'gompi',
            'toolchain_version': '1.4.10',
            'versionsuffix': '-OpenBLAS-0.2.6-LAPACK-3.4.2',
        }
        (generated, ec_file) = obtain_ec_for(specs, [test_easyconfigs_path])
        self.assertFalse(generated)
        self.assertEqual(os.path.basename(ec_file), 'ScaLAPACK-2.0.2-gompi-1.4.10-OpenBLAS-0.2.6-LAPACK-3.4.2.eb')

        specs = {
            'name': 'ifort',
            'versionsuffix': '-GCC-4.9.3-2.25',
        }
        (generated, ec_file) = obtain_ec_for(specs, [test_easyconfigs_path])
        self.assertFalse(generated)
        self.assertEqual(os.path.basename(ec_file), 'ifort-2016.1.150-GCC-4.9.3-2.25.eb')

        # latest version if not specified
        specs = {
            'name': 'GCC',
        }
        (generated, ec_file) = obtain_ec_for(specs, [test_easyconfigs_path])
        self.assertFalse(generated)
        self.assertEqual(os.path.basename(ec_file), 'GCC-4.9.2.eb')

        # generate non-existing easyconfig
        os.chdir(self.test_prefix)
        specs = {
            'name': 'GCC',
            'version': '5.4.3',
        }
        (generated, ec_file) = obtain_ec_for(specs, [test_easyconfigs_path])
        self.assertTrue(generated)
        self.assertEqual(os.path.basename(ec_file), 'GCC-5.4.3.eb')

    def test_tweak_one_version(self):
        """Test tweak_one function"""
        test_easyconfigs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'easyconfigs', 'test_ecs')
        toy_ec = os.path.join(test_easyconfigs_path, 't', 'toy', 'toy-0.0.eb')

        # test tweaking of software version (--try-software-version)
        tweaked_toy_ec = os.path.join(self.test_prefix, 'toy-tweaked.eb')
        tweak_one(toy_ec, tweaked_toy_ec, {'version': '1.2.3'})

        toy_ec_parsed = EasyConfigParser(toy_ec).get_config_dict()
        tweaked_toy_ec_parsed = EasyConfigParser(tweaked_toy_ec).get_config_dict()

        # checksums should be reset to empty list, only version should be changed, nothing else
        self.assertEqual(tweaked_toy_ec_parsed['checksums'], [])
        self.assertEqual(tweaked_toy_ec_parsed['version'], '1.2.3')
        for key in [k for k in toy_ec_parsed.keys() if k not in ['checksums', 'version']]:
            val = toy_ec_parsed[key]
            self.assertTrue(key in tweaked_toy_ec_parsed, "Parameter '%s' not defined in tweaked easyconfig file" % key)
            tweaked_val = tweaked_toy_ec_parsed.get(key)
            self.assertEqual(val, tweaked_val, "Different value for %s parameter: %s vs %s" % (key, val, tweaked_val))

        # check behaviour if target file already exists
        error_pattern = "A file already exists at .* where tweaked easyconfig file would be written"
        self.assertErrorRegex(EasyBuildError, error_pattern, tweak_one, toy_ec, tweaked_toy_ec, {'version': '1.2.3'})

        # existing file does get overwritten when --force is used
        build_options = {'force': True}
        init_config(build_options=build_options)
        write_file(tweaked_toy_ec, '')
        tweak_one(toy_ec, tweaked_toy_ec, {'version': '1.2.3'})
        tweaked_toy_ec_parsed = EasyConfigParser(tweaked_toy_ec).get_config_dict()
        self.assertEqual(tweaked_toy_ec_parsed['version'], '1.2.3')

    def test_compare_toolchain_specs(self):
        """Test comparing the functionality of two toolchains"""
        test_easyconfigs = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'easyconfigs', 'test_ecs')
        init_config(build_options={
            'valid_module_classes': module_classes(),
            'robot_path': test_easyconfigs,
        })
        get_toolchain_hierarchy.clear()
        goolf_hierarchy = get_toolchain_hierarchy({'name': 'goolf', 'version': '1.4.10'}, require_capabilities=True)
        iimpi_hierarchy = get_toolchain_hierarchy({'name': 'iimpi', 'version': '5.5.3-GCC-4.8.3'},
                                                  require_capabilities=True)

        # Hierarchies are returned with top-level toolchain last, goolf has 3 elements here, intel has 2
        # goolf <-> iimpi (should return False)
        self.assertFalse(compare_toolchain_specs(goolf_hierarchy[2], iimpi_hierarchy[1]), "goolf requires math libs")
        # gompi <-> iimpi
        self.assertTrue(compare_toolchain_specs(goolf_hierarchy[1], iimpi_hierarchy[1]))
        # GCC <-> iimpi
        self.assertTrue(compare_toolchain_specs(goolf_hierarchy[0], iimpi_hierarchy[1]))
        # GCC <-> iccifort
        self.assertTrue(compare_toolchain_specs(goolf_hierarchy[0], iimpi_hierarchy[0]))

    def test_match_minimum_tc_specs(self):
        """Test matching a toolchain to lowest possible in a hierarchy"""
        test_easyconfigs = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'easyconfigs', 'test_ecs')
        init_config(build_options={
            'valid_module_classes': module_classes(),
            'robot_path': test_easyconfigs,
        })
        get_toolchain_hierarchy.clear()
        goolf_hierarchy = get_toolchain_hierarchy({'name': 'goolf', 'version': '1.4.10'}, require_capabilities=True)
        iimpi_hierarchy = get_toolchain_hierarchy({'name': 'iimpi', 'version': '5.5.3-GCC-4.8.3'},
                                                  require_capabilities=True)

        # Compiler first
        self.assertEqual(match_minimum_tc_specs(iimpi_hierarchy[0], goolf_hierarchy),
                         {'name': 'GCC', 'version': '4.7.2'})
        # Then MPI
        self.assertEqual(match_minimum_tc_specs(iimpi_hierarchy[1], goolf_hierarchy),
                         {'name': 'gompi', 'version': '1.4.10'})
        # Check against itself for math
        self.assertEqual(match_minimum_tc_specs(goolf_hierarchy[2], goolf_hierarchy),
                         {'name': 'goolf', 'version': '1.4.10'})
        # Make sure there's an error when we can't do the mapping
        error_msg = "No possible mapping from source toolchain spec .*"
        self.assertErrorRegex(EasyBuildError, error_msg, match_minimum_tc_specs,
                              goolf_hierarchy[2], iimpi_hierarchy)

    def test_map_toolchain_hierarchies(self):
        """Test mapping between two toolchain hierarchies"""
        test_easyconfigs = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'easyconfigs', 'test_ecs')
        init_config(build_options={
            'valid_module_classes': module_classes(),
            'robot_path': test_easyconfigs,
        })
        get_toolchain_hierarchy.clear()
        goolf_tc = {'name': 'goolf', 'version': '1.4.10'}
        gompi_tc = {'name': 'gompi', 'version': '1.4.10'}
        iimpi_tc = {'name': 'iimpi', 'version': '5.5.3-GCC-4.8.3'}

        self.assertEqual(map_toolchain_hierarchies(iimpi_tc, goolf_tc, self.modtool),
                         {'iccifort': {'name': 'GCC', 'version': '4.7.2'},
                          'iimpi': {'name': 'gompi', 'version': '1.4.10'}})
        self.assertEqual(map_toolchain_hierarchies(gompi_tc, iimpi_tc, self.modtool),
                         {'GCC': {'name': 'iccifort', 'version': '2013.5.192-GCC-4.8.3'},
                          'gompi': {'name': 'iimpi', 'version': '5.5.3-GCC-4.8.3'}})
        # Expect an error when there is no possible mapping
        error_msg = "No possible mapping from source toolchain spec .*"
        self.assertErrorRegex(EasyBuildError, error_msg, map_toolchain_hierarchies,
                              goolf_tc, iimpi_tc, self.modtool)

        # Test that we correctly include GCCcore binutils when it is there
        gcc_binutils_tc = {'name': 'GCC', 'version': '4.9.3-2.25'}
        iccifort_binutils_tc = {'name': 'iccifort', 'version': '2016.1.150-GCC-4.9.3-2.25'}
        self.assertEqual(map_toolchain_hierarchies(gcc_binutils_tc, iccifort_binutils_tc, self.modtool),
                         {'GCC': {'name': 'iccifort', 'version': '2016.1.150-GCC-4.9.3-2.25'},
                          'GCCcore': {'name': 'GCCcore', 'version': '4.9.3'},
                          'binutils': {'version': '2.25', 'versionsuffix': ''}})

    def test_map_easyconfig_to_target_tc_hierarchy(self):
        """Test mapping of easyconfig to target hierarchy"""
        test_easyconfigs = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'easyconfigs', 'test_ecs')
        init_config(build_options={
            'valid_module_classes': module_classes(),
            'robot_path': test_easyconfigs,
        })
        get_toolchain_hierarchy.clear()
        gcc_binutils_tc = {'name': 'GCC', 'version': '4.9.3-2.25'}
        iccifort_binutils_tc = {'name': 'iccifort', 'version': '2016.1.150-GCC-4.9.3-2.25'}
        map_easyconfig_to_target_tc_hierarchy()

def suite():
    """ return all the tests in this file """
    return TestLoaderFiltered().loadTestsFromTestCase(TweakTest, sys.argv[1:])


if __name__ == '__main__':
    TextTestRunner(verbosity=1).run(suite())
