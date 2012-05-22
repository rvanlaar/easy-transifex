import os

# Django settings for nens_transifex project.
from transifex.settings import *

PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))
VAR_DIR = os.path.join(PROJECT_DIR, 'var')

# Make this unique, and don't share it with anybody.
SECRET_KEY = '65_ec2u#(!m=&=0oxi73q#9)y#5vfe%vdc_a5g=r%z!wv$)c#-'

## Transifex Config has the settings in a lot of files.
## Here are the specific nens_transifex overrides.

## 10-base.conf
LOG_PATH = os.path.join(VAR_DIR, 'log')
STATIC_ROOT = os.path.join(VAR_DIR, 'static')
MEDIA_ROOT = os.path.join(VAR_DIR, 'media')

## 30-site.conf
DEBUG = True
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
