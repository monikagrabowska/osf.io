from nose.tools import *  # flake8: noqa

from tests.base import ApiTestCase
from osf_tests.factories import InstitutionFactory

from website.models import Node
from api.base.settings.defaults import API_BASE

class TestInstitutionList(ApiTestCase):
    def setUp(self):
        super(TestInstitutionList, self).setUp()
        self.institution = InstitutionFactory()
        self.institution2 = InstitutionFactory()
        self.institution_url = '/{}institutions/'.format(API_BASE)

    def test_return_all_institutions(self):
        res = self.app.get(self.institution_url)

        assert_equal(res.status_code, 200)

        ids = [each['id'] for each in res.json['data']]
        assert_equal(len(res.json['data']), 2)
        assert_equal(res.json['links']['meta']['per_page'], 1000)
        assert_in(self.institution._id, ids)
        assert_in(self.institution2._id, ids)

    def test_does_not_return_deleted_institution(self):
        self.institution.is_deleted = True
        self.institution.save()

        res = self.app.get(self.institution_url)

        assert_equal(res.status_code, 200)

        ids = [each['id'] for each in res.json['data']]
        assert_equal(len(res.json['data']), 1)
        assert_not_in(self.institution._id, ids)
        assert_in(self.institution2._id, ids)
