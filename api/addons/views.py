import importlib

from rest_framework.exceptions import NotFound
from rest_framework import generics, permissions as drf_permissions

from framework.auth.oauth_scopes import CoreScopes

from api.addons.serializers import AddonSerializer
from api.base.permissions import TokenHasScope
from api.base.settings import ADDONS_OAUTH
from api.base.views import JSONAPIBaseView

from website import settings as osf_settings


class AddonSettingsMixin(object):
    """Mixin with convenience method for retrieving the current <Addon><Node|User>Settings based on the
    current URL. By default, fetches the settings based on the user or node available in self context.
    """

    def get_addon_settings(self, provider=None, fail_if_absent=True):
        owner = None
        provider = provider or self.kwargs['provider']

        if hasattr(self, 'get_user'):
            owner = self.get_user()
            owner_type = 'user'
        elif hasattr(self, 'get_node'):
            owner = self.get_node()
            owner_type = 'node'

        try:
            addon_module = importlib.import_module('website.addons.{}'.format(provider))
        except ImportError:
            raise NotFound('Requested addon unrecognized')

        if not owner or provider not in ADDONS_OAUTH or owner_type not in addon_module.OWNERS:
            raise NotFound('Requested addon unavailable')

        addon_settings = owner.get_addon(provider)
        if not addon_settings and fail_if_absent:
            raise NotFound('Requested addon not enabled')

        if not addon_settings or addon_settings.deleted:
            return None

        return addon_settings

class AddonList(JSONAPIBaseView, generics.ListAPIView):
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

    serializer_class = AddonSerializer
    view_category = 'addons'
    view_name = 'addon-list'

    def get_queryset(self):
        return [conf for conf in osf_settings.ADDONS_AVAILABLE_DICT.itervalues() if 'accounts' in conf.configs]
