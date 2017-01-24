# -*- coding: utf-8 -*-

# Copyright 2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import os
import shutil
import mock
import unittest
from collections import Counter

from botocore.compat import six
from mock import Mock

from ebcli.core import fileoperations
from ebcli.operations import commonops
from ebcli.lib.aws import InvalidParameterValueError
from ebcli.objects.buildconfiguration import BuildConfiguration
from ebcli.resources.strings import strings, responses

class TestCommonOperations(unittest.TestCase):
    app_name = 'ebcli-app'
    app_version_name = 'ebcli-app-version'
    env_name = 'ebcli-env'
    description = 'ebcli testing app'
    s3_bucket = 'app_bucket'
    s3_key = 'app_bucket_key'

    repository = 'my-repo'
    branch = 'my-branch'
    commit_id = '123456789'

    image = 'aws/codebuild/eb-java-8-amazonlinux-64:2.1.3'
    compute_type = 'BUILD_GENERAL1_SMALL'
    service_role = 'eb-test'
    service_role_arn = 'arn:testcli:eb-test'
    timeout = 60
    build_config = BuildConfiguration(image=image, compute_type=compute_type,
                                      service_role=service_role, timeout=timeout)


    def assertListsOfDictsEquivalent(self, ls1, ls2):
        return self.assertEqual(
            Counter(frozenset(six.iteritems(d)) for d in ls1),
            Counter(frozenset(six.iteritems(d)) for d in ls2))

    def setUp(self):
        # set up test directory
        if not os.path.exists('testDir'):
            os.makedirs('testDir')
        os.chdir('testDir')

        # set up mock elastic beanstalk directory
        if not os.path.exists(fileoperations.beanstalk_directory):
            os.makedirs(fileoperations.beanstalk_directory)

        # set up mock home dir
        if not os.path.exists('home'):
            os.makedirs('home')

        # change directory to mock home
        fileoperations.aws_config_folder = 'home' + os.path.sep
        fileoperations.aws_config_location \
            = fileoperations.aws_config_folder + 'config'

        # Create local
        fileoperations.create_config_file('ebcli-test', 'us-east-1',
                                          'my-solution-stack')

    def tearDown(self):
        os.chdir(os.path.pardir)
        if os.path.exists('testDir'):
            shutil.rmtree('testDir')

    def test_is_success_string(self):
        self.assertTrue(commonops._is_success_string('Environment health has been set to GREEN'))
        self.assertTrue(commonops._is_success_string('Successfully launched environment: my-env'))
        self.assertTrue(commonops._is_success_string('Pulled logs for environment instances.'))
        self.assertTrue(commonops._is_success_string('terminateEnvironment completed successfully.'))

    @mock.patch('ebcli.operations.commonops.SourceControl')
    def test_return_global_default_if_no_branch_default(self, mock):
        sc_mock = Mock()
        sc_mock.get_current_branch.return_value = 'none'
        mock.get_source_control.return_value = sc_mock

        result = commonops.get_config_setting_from_branch_or_default('default_region')
        assert sc_mock.get_current_branch.called, 'Should have been called'
        self.assertEqual(result, 'us-east-1')

        fileoperations.write_config_setting('global', 'default_region', 'brazil')
        fileoperations.write_config_setting('global', 'profile', 'monica')
        fileoperations.write_config_setting('global', 'moop', 'meep')
        fileoperations.write_config_setting('branch-defaults', 'my-branch', {'profile': 'chandler',
            'environment': 'my-env', 'boop': 'beep'})

        result = commonops.get_current_branch_environment()
        self.assertEqual(result, None)

        # get default profile name
        result = commonops.get_default_profile()
        self.assertEqual(result, 'monica')

        result = commonops.get_config_setting_from_branch_or_default('moop')
        self.assertEqual(result, 'meep')


    @mock.patch('ebcli.operations.commonops.SourceControl')
    def test_return_branch_default_if_set(self, mock):
        sc_mock = Mock()
        sc_mock.get_current_branch.return_value = 'my-branch'
        mock.get_source_control.return_value = sc_mock

        fileoperations.write_config_setting('global', 'default_region', 'brazil')
        fileoperations.write_config_setting('global', 'profile', 'monica')
        fileoperations.write_config_setting('global', 'moop', 'meep')
        fileoperations.write_config_setting('branch-defaults', 'my-branch', {'profile': 'chandler',
            'environment': 'my-env', 'boop': 'beep'})

        # get default region name
        result = commonops.get_default_region()
        self.assertEqual(result, 'brazil')

        # get branch-specific default environment name
        result = commonops.get_current_branch_environment()
        self.assertEqual(result, 'my-env')

        # get branch-specific default profile name
        result = commonops.get_default_profile()
        self.assertEqual(result, 'chandler')

        # get branch-specific generic default
        result = commonops.get_config_setting_from_branch_or_default('boop')
        self.assertEqual(result, 'beep')

    def test_create_envvars_list_empty(self):
        options, options_to_remove = commonops.create_envvars_list([])
        self.assertEqual(options, list())
        self.assertEqual(options_to_remove, list())

        options, options_to_remove = commonops.create_envvars_list(
            [], as_option_settings=False)
        self.assertEqual(options, dict())
        self.assertEqual(options_to_remove, set())

    def test_create_envvars_list_simple(self):
        namespace = 'aws:elasticbeanstalk:application:environment'

        options, options_to_remove = commonops.create_envvars_list(
            ['foo=bar'])
        self.assertListsOfDictsEquivalent(options, [
            dict(Namespace=namespace,
                 OptionName='foo',
                 Value='bar')])
        self.assertListEqual(options_to_remove, list())

        options, options_to_remove = commonops.create_envvars_list(
            ['foo=bar', 'fish=good'])
        self.assertListsOfDictsEquivalent(options, [
            dict(Namespace=namespace,
                 OptionName='foo',
                 Value='bar'),
            dict(Namespace=namespace,
                 OptionName='fish',
                 Value='good')])
        self.assertEqual(options_to_remove, list())

        options, options_to_remove = commonops.create_envvars_list(
            ['foo=bar', 'fish=good', 'trout=', 'baz='])
        self.assertListsOfDictsEquivalent(options, [
            dict(Namespace=namespace,
                 OptionName='foo',
                 Value='bar'),
            dict(Namespace=namespace,
                 OptionName='fish',
                 Value='good')])
        self.assertListsOfDictsEquivalent(options_to_remove, [
            dict(Namespace=namespace,
                 OptionName='trout'),
            dict(Namespace=namespace,
                 OptionName='baz')])

    def test_create_envvars_not_as_option_settings(self):
        options, options_to_remove = commonops.create_envvars_list(
            ['foo=bar'], as_option_settings=False)
        self.assertEqual(options, dict(foo='bar'))
        self.assertEqual(options_to_remove, set())

        options, options_to_remove = commonops.create_envvars_list(
            ['foo=bar', 'fish=good'], as_option_settings=False)
        self.assertDictEqual(options, dict(foo='bar', fish='good'))
        self.assertEqual(options_to_remove, set())

        options, options_to_remove = commonops.create_envvars_list(
            ['foo=bar', 'fish=good', 'trout=', 'baz='],
            as_option_settings=False)
        self.assertDictEqual(options, dict(foo='bar', fish='good'))
        self.assertEqual(options_to_remove, {'trout', 'baz'})

    def test_create_envvars_crazy_characters(self):
        string1 = 'http://some.url.com/?quer=true&othersutff=1'
        string2 = 'some other !@=:;#$%^&*() weird, key'

        options, options_to_remove = commonops.create_envvars_list(
            ['foo=' + string1,
             'wierd er value='+ string2], as_option_settings=False)
        self.assertEqual(options, {
            'foo': string1,
            'wierd er value': string2})
        self.assertEqual(options_to_remove, set())

    def test_create_envvars_not_bad_characters(self):
        strings = [
            '!hello',
            ',hello',
            '?hello',
            ';hello',
            '=hello',
            '$hello',
            '%hello',
            '😊'
        ]
        for s in strings:
            options, options_to_remove = commonops.create_envvars_list(
                ['foo=' + s], as_option_settings=False)
            self.assertEqual(options, {'foo': s})

    @mock.patch('ebcli.operations.commonops.elasticbeanstalk')
    def test_create_application_version_wrapper(self, mock_beanstalk):
        # Make the actual call
        actual_return = commonops._create_application_version(self.app_name, self.app_version_name,
                                              self.description, self.s3_bucket, self.s3_key)

        # Assert return and methods were called for the correct workflow
        self.assertEqual(self.app_version_name, actual_return, "Expected {0} but got: {1}"
                         .format(self.app_version_name, actual_return))
        mock_beanstalk.create_application_version.assert_called_with(self.app_name, self.app_version_name,
                                                                     self.description, self.s3_bucket, self.s3_key,
                                                                     False, None, None, None)

    @mock.patch('ebcli.operations.commonops.elasticbeanstalk')
    def test_create_application_version_wrapper_app_version_already_exists(self, mock_beanstalk):
        # Mock out methods
        mock_beanstalk.create_application_version.side_effect = InvalidParameterValueError('Application Version {0} already exists.'
                                                                .format(self.app_version_name))

        # Make the actual call
        actual_return = commonops._create_application_version(self.app_name, self.app_version_name,
                                              self.description, self.s3_bucket, self.s3_key)

        # Assert return and methods were called for the correct workflow
        self.assertEqual(self.app_version_name, actual_return, "Expected {0} but got: {1}"
                         .format(self.app_version_name, actual_return))
        mock_beanstalk.create_application_version.assert_called_with(self.app_name, self.app_version_name,
                                                                     self.description, self.s3_bucket, self.s3_key,
                                                                     False, None, None, None)

    @mock.patch('ebcli.operations.commonops.elasticbeanstalk')
    @mock.patch('ebcli.operations.commonops.fileoperations')
    def test_create_application_version_wrapper_app_does_not_exist(self, mock_fileoperations, mock_beanstalk):
        # Mock out methods
        mock_beanstalk.create_application_version.side_effect = [InvalidParameterValueError(responses['app.notexists'].replace(
                                                                '{app-name}', '\'' + self.app_name + '\'')), None]

        with mock.patch('ebcli.objects.sourcecontrol.Git') as MockGitClass:
            mock_git_sourcecontrol = MockGitClass.return_value
            mock_git_sourcecontrol.get_current_branch.return_value = self.branch
            with mock.patch('ebcli.operations.commonops.SourceControl') as MockSourceControlClass:
                mock_sourcecontrol = MockSourceControlClass.return_value
                mock_sourcecontrol.get_source_control.return_value = mock_git_sourcecontrol

            # Make the actual call
            actual_return = commonops._create_application_version(self.app_name, self.app_version_name,
                                          self.description, self.s3_bucket, self.s3_key)

        # Assert return and methods were called for the correct workflow
        self.assertEqual(self.app_version_name, actual_return, "Expected {0} but got: {1}"
                         .format(self.app_version_name, actual_return))
        mock_beanstalk.create_application_version.assert_called_with(self.app_name, self.app_version_name,
                                                                     self.description, self.s3_bucket, self.s3_key,
                                                                     False, None, None, None)
        mock_beanstalk.create_application.assert_called_with(self.app_name, strings['app.description'])

        write_config_calls = [mock.call('branch-defaults', self.branch, {'environment': None}),
                             mock.call('branch-defaults', self.branch, {'group_suffix': None})]
        mock_fileoperations.write_config_setting.assert_has_calls(write_config_calls)

    @mock.patch('ebcli.operations.commonops.elasticbeanstalk')
    def test_create_application_version_wrapper_app_version_throws_unknown_exception(self, mock_beanstalk):
        # Mock out methods
        mock_beanstalk.create_application_version.side_effect = Exception("FooException")

        # Make the actual call
        self.assertRaises(Exception, commonops._create_application_version, self.app_name, self.app_version_name,
                          self.description, self.s3_bucket, self.s3_key)

    @mock.patch('ebcli.operations.commonops.elasticbeanstalk')
    def test_create_application_version_wrapper_with_build_config(self, mock_beanstalk):
        # Mock out methods
        with mock.patch('ebcli.lib.iam.get_roles') as mock_iam_get_roles:
            mock_iam_get_roles.return_value = [{'RoleName': self.service_role, 'Arn': self.service_role_arn},
                                               {'RoleName': self.service_role, 'Arn': self.service_role_arn}]

            # Make the actual call
            actual_return = commonops._create_application_version(self.app_name, self.app_version_name,
                                                  self.description, self.s3_bucket, self.s3_key, build_config=self.build_config)

        # Assert return and methods were called for the correct workflow
        self.assertEqual(self.app_version_name, actual_return, "Expected {0} but got: {1}"
                         .format(self.app_version_name, actual_return))
        mock_beanstalk.create_application_version.assert_called_with(self.app_name, self.app_version_name,
                                                                     self.description, self.s3_bucket, self.s3_key,
                                                                     False, None, None, self.build_config)