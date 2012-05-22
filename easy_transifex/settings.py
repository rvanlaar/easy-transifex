import os

# Django settings for easy_transifex project.
from transifex.settings import *

PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))
VAR_DIR = os.path.join(PROJECT_DIR, 'var')

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'CHANGE THIS'

## Transifex Config has the settings in a lot of files.
## Here are the specific easy_transifex overrides.

## 10-base.conf
LOG_PATH = os.path.join(VAR_DIR, 'log')
STATIC_ROOT = os.path.join(VAR_DIR, 'static')
MEDIA_ROOT = os.path.join(VAR_DIR, 'media')

## 30-site.conf
DEBUG = False
TEMPLATE_DEBUG = DEBUG
SERVE_MEDIA = DEBUG

## 40-apps.conf
SCRATCH_DIR = os.path.join(VAR_DIR, 'scratchdir')

## 50-project.conf
INSTALLED_APPS += ['gunicorn']

## 55-haystack.conf
HAYSTACK_SEARCH_ENGINE = 'solr'

## 80-storage.conf
STORAGE_DIR = os.path.join(SCRATCH_DIR, 'storage_files')
