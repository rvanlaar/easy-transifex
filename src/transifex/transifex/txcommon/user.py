# -*- coding: utf-8 -*-
"""
User related class and functions.
"""

from userena.models import UserenaSignup


class CreateUserFromSocial(object):
    """Create local users from a social auth mechanism.

    Perform every step to create new users to the system. This is a
    wrapper around userena.
    """

    def __call__(self, *args, **kwargs):
        """Create a new user to Transifex.

        For now, this is copied from social_auth.backends.pipeline.user.
        """
        user = kwargs.get('user')
        if user is not None:
            return {'user': user}
        username = kwargs.get('username')
        if username is None:
            return None
        details = kwargs.get('details')
        if details is not None:
            email = details.get('email')
        user = UserenaSignup.objects.create_user(
            username, email, password=None, active=True, send_email=False
        )
        return {'user': user, 'is_new': True}


create_user = CreateUserFromSocial()
