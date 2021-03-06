# -*- coding: utf-8 -*-

from nose.tools import *  # noqa (PEP8 asserts)

import pytest
from osf_tests.factories import (
    ProjectFactory,
    UserFactory,
    RegistrationFactory,
    NodeFactory,
    CollectionFactory,
    BookmarkCollectionFactory,
)
from tests.base import OsfTestCase

from framework.auth import Auth
from framework import utils as framework_utils
from website.project.views.node import _get_summary, _view_project, _serialize_node_search, _get_children
from website.views import _render_node
from website.profile import utils
from website import filters, settings
from website.util import permissions

pytestmark = pytest.mark.django_db

class TestUserSerializers(OsfTestCase):
    def test_serialize_user(self):
        master = UserFactory()
        user = UserFactory()
        master.merge_user(user)
        d = utils.serialize_user(user)
        assert_equal(d['id'], user._primary_key)
        assert_equal(d['url'], user.url)
        assert_equal(d.get('username', None), None)
        assert_equal(d['fullname'], user.fullname)
        assert_equal(d['registered'], user.is_registered)
        assert_equal(d['absolute_url'], user.absolute_url)
        assert_equal(d['date_registered'], user.date_registered.strftime('%Y-%m-%d'))
        assert_equal(d['active'], user.is_active)

    def test_serialize_user_merged(self):
        master = UserFactory()
        user = UserFactory()
        master.merge_user(user)
        d = utils.serialize_user(user, full=True)
        assert_true(d['is_merged'])
        assert_equal(d['merged_by']['url'], user.merged_by.url)
        assert_equal(d['merged_by']['absolute_url'], user.merged_by.absolute_url)

    def test_serialize_user_full(self):
        user = UserFactory()
        ProjectFactory(creator=user, is_public=False)
        NodeFactory(creator=user)
        ProjectFactory(creator=user, is_public=True)
        CollectionFactory(creator=user)
        d = utils.serialize_user(user, full=True)
        gravatar = filters.gravatar(
            user,
            use_ssl=True,
            size=settings.PROFILE_IMAGE_LARGE
        )
        assert_equal(d['id'], user._primary_key)
        assert_equal(d['url'], user.url)
        assert_equal(d.get('username'), None)
        assert_equal(d['fullname'], user.fullname)
        assert_equal(d['registered'], user.is_registered)
        assert_equal(d['gravatar_url'], gravatar)
        assert_equal(d['absolute_url'], user.absolute_url)
        assert_equal(d['date_registered'], user.date_registered.strftime('%Y-%m-%d'))
        projects = [
            node
            for node in user.contributed
            if node.category == 'project'
            and not node.is_registration
            and not node.is_deleted
        ]
        public_projects = [p for p in projects if p.is_public]
        assert_equal(d['number_projects'], len(projects))
        assert_equal(d['number_public_projects'], len(public_projects))


class TestNodeSerializers(OsfTestCase):

    # Regression test for #489
    # https://github.com/CenterForOpenScience/openscienceframework.org/issues/489
    def test_get_summary_private_node_should_include_id_and_primary_boolean_reg_and_fork(self):
        user = UserFactory()
        # user cannot see this node
        node = ProjectFactory(is_public=False)
        result = _get_summary(
            node, auth=Auth(user),
            primary=True,
        )

        # serialized result should have id and primary
        assert_equal(result['summary']['id'], node._primary_key)
        assert_true(result['summary']['primary'], True)
        assert_equal(result['summary']['is_registration'], node.is_registration)
        assert_equal(result['summary']['is_fork'], node.is_fork)

    # https://github.com/CenterForOpenScience/openscienceframework.org/issues/668
    def test_get_summary_for_registration_uses_correct_date_format(self):
        reg = RegistrationFactory()
        res = _get_summary(reg, auth=Auth(reg.creator))
        assert_equal(res['summary']['registered_date'],
                reg.registered_date.strftime('%Y-%m-%d %H:%M UTC'))

    # https://github.com/CenterForOpenScience/openscienceframework.org/issues/858
    def test_get_summary_private_registration_should_include_is_registration(self):
        user = UserFactory()
        # non-contributor cannot see private registration of public project
        node = ProjectFactory(is_public=True)
        reg = RegistrationFactory(project=node, user=node.creator)
        res = _get_summary(reg, auth=Auth(user))

        # serialized result should have is_registration
        assert_true(res['summary']['is_registration'])

    def test_render_node(self):
        node = ProjectFactory()
        res = _render_node(node)
        assert_equal(res['title'], node.title)
        assert_equal(res['id'], node._primary_key)
        assert_equal(res['url'], node.url)
        assert_equal(res['api_url'], node.api_url)
        assert_equal(res['primary'], node.primary)
        assert_equal(res['date_modified'], framework_utils.iso8601format(node.date_modified))
        assert_equal(res['category'], 'project')
        assert_false(res['is_registration'])
        assert_false(res['is_retracted'])

    def test_render_node_returns_permissions(self):
        node = ProjectFactory()
        admin = UserFactory()
        node.add_contributor(admin, auth=Auth(node.creator),
            permissions=permissions.expand_permissions(permissions.ADMIN))
        writer = UserFactory()
        node.add_contributor(writer, auth=Auth(node.creator),
            permissions=permissions.expand_permissions(permissions.WRITE))
        node.save()

        res_admin = _render_node(node, Auth(admin))
        assert_equal(res_admin['permissions'], 'admin')
        res_writer = _render_node(node, Auth(writer))
        assert_equal(res_writer['permissions'], 'write')

    # https://openscience.atlassian.net/browse/OSF-4618
    def test_get_children_only_returns_child_nodes_with_admin_permissions(self):
        user = UserFactory()
        admin_project = ProjectFactory()
        admin_project.add_contributor(user, auth=Auth(admin_project.creator),
                                      permissions=permissions.expand_permissions(permissions.ADMIN))
        admin_project.save()

        admin_component = NodeFactory(parent=admin_project)
        admin_component.add_contributor(user, auth=Auth(admin_component.creator),
                                        permissions=permissions.expand_permissions(permissions.ADMIN))
        admin_component.save()

        read_and_write = NodeFactory(parent=admin_project)
        read_and_write.add_contributor(user, auth=Auth(read_and_write.creator),
                                       permissions=permissions.expand_permissions(permissions.WRITE))
        read_and_write.save()
        read_only = NodeFactory(parent=admin_project)
        read_only.add_contributor(user, auth=Auth(read_only.creator),
                                  permissions=permissions.expand_permissions(permissions.READ))
        read_only.save()

        non_contributor = NodeFactory(parent=admin_project)
        components = _get_children(admin_project, Auth(user))
        assert_equal(len(components), 1)

    def test_get_summary_private_fork_should_include_is_fork(self):
        user = UserFactory()
        # non-contributor cannot see private fork of public project
        node = ProjectFactory(is_public=True)
        consolidated_auth = Auth(user=node.creator)
        fork = node.fork_node(consolidated_auth)

        res = _get_summary(
            fork, auth=Auth(user),
            primary=True,
        )
        # serialized result should have is_fork
        assert_true(res['summary']['is_fork'])

    def test_get_summary_private_fork_private_project_should_include_is_fork(self):
        # contributor on a private project
        user = UserFactory()
        node = ProjectFactory(is_public=False)
        node.add_contributor(user)

        # contributor cannot see private fork of this project
        consolidated_auth = Auth(user=node.creator)
        fork = node.fork_node(consolidated_auth)

        res = _get_summary(
            fork, auth=Auth(user),
            primary=True,
        )
        # serialized result should have is_fork
        assert_false(res['summary']['can_view'])
        assert_true(res['summary']['is_fork'])

    def test_serialize_node_search_returns_only_visible_contributors(self):
        node = NodeFactory()
        non_visible_contributor = UserFactory()
        node.add_contributor(non_visible_contributor, visible=False)
        serialized_node = _serialize_node_search(node)

        assert_equal(serialized_node['firstAuthor'], node.visible_contributors[0].family_name)
        assert_equal(len(node.visible_contributors), 1)
        assert_false(serialized_node['etal'])


class TestViewProject(OsfTestCase):

    def setUp(self):
        super(TestViewProject, self).setUp()
        self.user = UserFactory()
        self.node = ProjectFactory(creator=self.user)

    # related to https://github.com/CenterForOpenScience/openscienceframework.org/issues/1109
    def test_view_project_pointer_count_excludes_folders(self):
        pointer_project = ProjectFactory(is_public=True)  # project that points to another project
        pointed_project = self.node  # project that other project points to
        pointer_project.add_pointer(pointed_project, Auth(pointer_project.creator), save=True)

        # Project is in a organizer collection
        folder = CollectionFactory(creator=pointed_project.creator)
        folder.add_pointer(pointed_project, Auth(pointed_project.creator), save=True)

        result = _view_project(pointed_project, Auth(pointed_project.creator))
        # pointer_project is included in count, but not folder
        assert_equal(result['node']['points'], 1)

    def test_view_project_pending_registration_for_admin_contributor_does_contain_cancel_link(self):
        pending_reg = RegistrationFactory(project=self.node, archive=True)
        assert_true(pending_reg.is_pending_registration)
        result = _view_project(pending_reg, Auth(self.user))

        assert_not_equal(result['node']['disapproval_link'], '')
        assert_in('/?token=', result['node']['disapproval_link'])
        pending_reg.remove()

    def test_view_project_pending_registration_for_write_contributor_does_not_contain_cancel_link(self):
        write_user = UserFactory()
        self.node.add_contributor(write_user, permissions=permissions.WRITE,
                                  auth=Auth(self.user), save=True)
        pending_reg = RegistrationFactory(project=self.node, archive=True)
        assert_true(pending_reg.is_pending_registration)
        result = _view_project(pending_reg, Auth(write_user))

        assert_equal(result['node']['disapproval_link'], '')
        pending_reg.remove()


class TestNodeLogSerializers(OsfTestCase):

    def test_serialize_node_for_logs(self):
        node = NodeFactory()
        d = node.serialize()

        assert_equal(d['id'], node._primary_key)
        assert_equal(d['category'], node.category_display)
        assert_equal(d['node_type'], node.project_or_component)
        assert_equal(d['url'], node.url)
        assert_equal(d['title'], node.title)
        assert_equal(d['api_url'], node.api_url)
        assert_equal(d['is_public'], node.is_public)
        assert_equal(d['is_registration'], node.is_registration)


class TestAddContributorJson(OsfTestCase):

    def setUp(self):
        super(TestAddContributorJson, self).setUp()
        self.user = UserFactory()
        self.profile = self.user.profile_url
        self.user_id = self.user._primary_key
        self.fullname = self.user.fullname
        self.username = self.user.username

        self.jobs = [{
            'institution': 'School of Lover Boys',
            'department': 'Fancy Patter',
            'title': 'Lover Boy',
            'start': None,
            'end': None,
        }]

        self.schools = [{
            'degree': 'Vibing',
            'institution': 'Queens University',
            'department': '',
            'location': '',
            'start': None,
            'end': None,
        }]

    def test_add_contributor_json(self):
        # User with no employment or education info listed
        user_info = utils.add_contributor_json(self.user)

        assert_equal(user_info['fullname'], self.fullname)
        assert_equal(user_info['email'], self.username)
        assert_equal(user_info['id'], self.user_id)
        assert_equal(user_info['employment'], None)
        assert_equal(user_info['education'], None)
        assert_equal(user_info['n_projects_in_common'], 0)
        assert_equal(user_info['registered'], True)
        assert_equal(user_info['active'], True)
        assert_in('secure.gravatar.com', user_info['gravatar_url'])
        assert_equal(user_info['profile_url'], self.profile)

    def test_add_contributor_json_with_edu(self):
        # Test user with only education information
        self.user.schools = self.schools
        user_info = utils.add_contributor_json(self.user)

        assert_equal(user_info['fullname'], self.fullname)
        assert_equal(user_info['email'], self.username)
        assert_equal(user_info['id'], self.user_id)
        assert_equal(user_info['employment'], None)
        assert_equal(user_info['education'], self.user.schools[0]['institution'])
        assert_equal(user_info['n_projects_in_common'], 0)
        assert_equal(user_info['registered'], True)
        assert_equal(user_info['active'], True)
        assert_in('secure.gravatar.com', user_info['gravatar_url'])
        assert_equal(user_info['profile_url'], self.profile)

    def test_add_contributor_json_with_job(self):
        # Test user with only employment information
        self.user.jobs = self.jobs
        user_info = utils.add_contributor_json(self.user)

        assert_equal(user_info['fullname'], self.fullname)
        assert_equal(user_info['email'], self.username)
        assert_equal(user_info['id'], self.user_id)
        assert_equal(user_info['employment'], self.user.jobs[0]['institution'])
        assert_equal(user_info['education'], None)
        assert_equal(user_info['n_projects_in_common'], 0)
        assert_equal(user_info['registered'], True)
        assert_equal(user_info['active'], True)
        assert_in('secure.gravatar.com', user_info['gravatar_url'])
        assert_equal(user_info['profile_url'], self.profile)

    def test_add_contributor_json_with_job_and_edu(self):
        # User with both employment and education information
        self.user.jobs = self.jobs
        self.user.schools = self.schools
        user_info = utils.add_contributor_json(self.user)

        assert_equal(user_info['fullname'], self.fullname)
        assert_equal(user_info['email'], self.username)
        assert_equal(user_info['id'], self.user_id)
        assert_equal(user_info['employment'], self.user.jobs[0]['institution'])
        assert_equal(user_info['education'], self.user.schools[0]['institution'])
        assert_equal(user_info['n_projects_in_common'], 0)
        assert_equal(user_info['registered'], True)
        assert_equal(user_info['active'], True)
        assert_in('secure.gravatar.com', user_info['gravatar_url'])
        assert_equal(user_info['profile_url'], self.profile)
