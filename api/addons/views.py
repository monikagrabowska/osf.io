from django.apps import apps
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework import generics, permissions as drf_permissions

from framework.auth.oauth_scopes import CoreScopes

from api.addons.serializers import AddonSerializer
from api.base.filters import ListFilterMixin
from api.base.pagination import MaxSizePagination
from api.base.permissions import TokenHasScope
from api.base.settings import ADDONS_OAUTH
from api.base.views import JSONAPIBaseView

from website import settings as osf_settings


class AddonSettingsMixin(object):
    """Mixin with convenience method for retrieving the current <Addon><Node|User>Settings based on the
    current URL. By default, fetches the settings based on the user or node available in self context.
    """

    def get_addon_settings(self, provider=None, fail_if_absent=True, check_object_permissions=True):
        owner = None
        provider = provider or self.kwargs['provider']

        if hasattr(self, 'get_user'):
            owner = self.get_user()
            owner_type = 'user'
        elif hasattr(self, 'get_node'):
            owner = self.get_node()
            owner_type = 'node'

        try:
            addon_module = apps.get_app_config('addons_{}'.format(provider))
        except LookupError:
            raise NotFound('Requested addon unrecognized')

        if not owner or provider not in ADDONS_OAUTH or owner_type not in addon_module.owners:
            raise NotFound('Requested addon unavailable')

        addon_settings = owner.get_addon(provider)
        if not addon_settings and fail_if_absent:
            raise NotFound('Requested addon not enabled')

        if not addon_settings or addon_settings.deleted:
            return None

        if addon_settings and check_object_permissions:
            authorizer = None
            if owner_type == 'user':
                authorizer = addon_settings.owner
            elif hasattr(addon_settings, 'user_settings'):
                authorizer = addon_settings.user_settings.owner
            if authorizer and authorizer != self.request.user:
                raise PermissionDenied('Must be addon authorizer to list folders')

        return addon_settings

class AddonList(JSONAPIBaseView, generics.ListAPIView, ListFilterMixin):
    """List of addons configurable with the OSF *Read-only*.

    Paginated list of addons associated with third-party services

    ##Permissions

    No restrictions.

    ## <Addon> Attributes

    OSF <Addon\> entities have the "addons" `type`, and their `id` indicates the
    `short_name` of the associated service provider (eg. `box`, `googledrive`, etc).

        name        type        description
        ======================================================================================================
        url         string      Url of this third-party service
        name        string      `full_name` of third-party service provider
        description string      Description of this addon
        categories  list        List of categories this addon belongs to

    #This Request/Response
    """
    permission_classes = (
        drf_permissions.AllowAny,
        drf_permissions.IsAuthenticatedOrReadOnly,
        TokenHasScope, )

    required_read_scopes = [CoreScopes.ALWAYS_PUBLIC]
    required_write_scopes = [CoreScopes.NULL]

    pagination_class = MaxSizePagination
    serializer_class = AddonSerializer
    view_category = 'addons'
    view_name = 'addon-list'

    def get_default_queryset(self):
        return [conf for conf in osf_settings.ADDONS_AVAILABLE_DICT.itervalues() if 'accounts' in conf.configs]

    def get_queryset(self):
        return self.get_queryset_from_request()
