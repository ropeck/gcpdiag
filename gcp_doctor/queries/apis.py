# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Lint as: python3
"""Build and cache GCP APIs + handle authentication."""

import json
import logging
import os
import pkgutil
import sys
from typing import Dict

import google_auth_httplib2
import googleapiclient.http
import httplib2
from google.auth import exceptions
from google.auth.transport import requests
from google_auth_oauthlib import flow
from googleapiclient import discovery

from gcp_doctor import caching

_credentials = None


def _get_credentials():
  global _credentials

  # If we have no credentials in memory, fetch from the disk cache.
  if not _credentials:
    with caching.get_cache() as diskcache:
      _credentials = diskcache.get('credentials')

  # Try to refresh the credentials.
  if _credentials and _credentials.expired and _credentials.refresh_token:
    try:
      logging.debug('refreshing credentials')
      _credentials.refresh(requests.Request())
      # Store the refreshed credentials.
      with caching.get_cache() as diskcache:
        diskcache.set('credentials', _credentials)
    except exceptions.RefreshError as e:
      logging.debug("couldn't refresh token: %s", e)

  # Login using browser and verification code.
  if not _credentials or not _credentials.valid:
    logging.debug('No valid credentials found. Initiating auth flow.')
    client_config = json.loads(
        pkgutil.get_data('gcp_doctor.queries', 'client_secrets.json'))
    oauth_flow = flow.Flow.from_client_config(
        client_config,
        scopes=[
            'openid',
            'https://www.googleapis.com/auth/cloud-platform',
            'https://www.googleapis.com/auth/accounts.reauth',
            'https://www.googleapis.com/auth/userinfo.email',
        ],
        redirect_uri='urn:ietf:wg:oauth:2.0:oob')
    auth_url, _ = oauth_flow.authorization_url(prompt='consent')
    print('Go to the following URL in your browser to authenticate:\n',
          file=sys.stderr)
    print('  ' + auth_url, file=sys.stderr)
    print('\nEnter verification code: ', file=sys.stderr, end='')
    code = input()
    print(file=sys.stderr)
    oauth_flow.fetch_token(code=code)
    _credentials = oauth_flow.credentials

    # Store the credentials in the disk cache.
    with caching.get_cache() as diskcache:
      diskcache.set('credentials', _credentials)

  return _credentials


def login():
  """Force GCP login (this otherwise happens on the first get_api call)."""
  _get_credentials()
  if os.getenv('GOOGLE_AUTH_TOKEN'):
    logging.warning(
        'Using IAM authorization token from GOOGLE_AUTH_TOKEN env. variable.')


def get_user_email() -> str:
  credentials = _get_credentials()
  http = httplib2.Http()
  headers: Dict[str, str] = {}
  credentials.apply(headers)
  resp, content = http.request('https://www.googleapis.com/userinfo/v2/me',
                               'GET',
                               headers=headers)
  if resp['status'] != '200':
    raise RuntimeError(f"can't determine user email. status={resp['status']}")
  data = json.loads(content)
  return data['email']


@caching.cached_api_call(in_memory=True)
def get_api(service_name: str, version: str):
  credentials = _get_credentials()

  def _request_builder(http, *args, **kwargs):
    del http

    try:
      # This is for Google-internal use only and allows us to modify the request
      # to make it work also internally. The import will fail for the public
      # version of gcp-doctor.
      # pylint: disable=import-outside-toplevel
      from gcp_doctor_google_internal import hooks
      hooks.request_builder_hook(*args, **kwargs)
    except ImportError:
      pass

    # thread safety: create a new AuthorizedHttp object for every request
    # https://github.com/googleapis/google-api-python-client/blob/master/docs/thread_safety.md
    new_http = google_auth_httplib2.AuthorizedHttp(credentials,
                                                   http=httplib2.Http())
    return googleapiclient.http.HttpRequest(new_http, *args, **kwargs)

  api = discovery.build(service_name,
                        version,
                        cache_discovery=False,
                        credentials=credentials,
                        requestBuilder=_request_builder)
  return api
