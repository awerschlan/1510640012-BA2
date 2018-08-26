#!/opt/vtse/bin/python
import os, sys
sys.path = [os.path.dirname(__file__)] + sys.path
os.chdir(os.path.dirname(__file__))
import autotrader_rest_main
def application(environ, start_response):
     environ['wsgi.url_scheme'] = 'https'
     return autotrader_rest_main.app(environ, start_response)
