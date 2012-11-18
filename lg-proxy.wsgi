
import sys
import os

sitepath = os.path.realpath(os.path.dirname(__file__))
sys.path.insert(0, sitepath)

from lg_proxy import app as application
