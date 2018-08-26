#!/usr/bin/env python2.7
import sys
import requests
from requests.auth import HTTPBasicAuth
try:
    import json
except ImportError:
    import simplejson as json

import logging
logging.basicConfig() # you need to initialize logging, otherwise you will not see anything from requests
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

api_user = ''
api_password = ''
api_base_url = 'https://portal-test.visotech.com/jira/rest/insight/1.0'

schema_name = 'Infrastructure'
objecttype_name = 'Server'

limit = '1000'      # number of hosts to list


def get_schema_id(session):
    # authenticate and get schema id
    response_objectschemas = session.get(api_base_url + '/objectschema/list', auth=HTTPBasicAuth(api_user, api_password))
    for schema in response_objectschemas.json()['objectschemas']:
        if schema['name'] == schema_name:
            return schema['id']

def get_objecttype_id(session, schema_id):
    # get objecttype id using schema id
    response_objecttypes = session.get(api_base_url + '/objectschema/' + schema_id + '/objecttypes/flat')
    for objecttype in response_objecttypes.json():
        if objecttype['name'] == objecttype_name:
            return objecttype['id']

def get_object_id(session, name):
    response_objects = session.get(api_base_url + '/objecttype/' + objecttype_id + '/objects?query=' + name)
    return response_objects.json()[0]['id']

def get_objects(session):
    response_objects = session.get(api_base_url + '/objecttype/' + objecttype_id + '/objects?limit=' + limit)
    return response_objects.json()

def get_object_attributes(session, name):
    # use object id to get object attributes
    response_object_attributes = session.get(api_base_url + '/object/' +  str(get_object_id(session, name)) + '/attributes')
    return response_object_attributes.json()

def print_grouplist(session, schema_id, objecttype_id):
    inventory = {}
    # inventory['local'] = [ '127.0.0.1' ]
    # all hosts are in one group, for now (hostgroups will be implemented in Insight in the future)
    inventory['all'] = {
        'hosts' : []
    }

    # works, but is too slow (two additional API Requests for each Server)
    # for object in get_objects(session):
    #     for attribute in get_object_attributes(session, object['label']):
    #         if attribute['objectTypeAttribute']['name'] == 'Status' and attribute['objectAttributeValues'][0]['displayValue'] == 'Active':
    #               inventory['all']['hosts'].append(object['label'])

    # for performance: use filtering via IQL and one single API Request instead
    post_data = { "objectSchemaId": schema_id, "objectTypeId": objecttype_id, "page": 1, "resultsPerPage": limit, "includeAttributes": "false", "iql": "Status IN Active" }

    response_objectEntries = session.post(api_base_url + '/object/navlist/iql', json=post_data)

    for entry in response_objectEntries.json()['objectEntries']:
        inventory['all']['hosts'].append(entry['label'])

    print json.dumps(inventory, indent=4)

def print_hostvars(session, name):

    hostvars = {}

    # insert server roles and ansible hostvars
    for attribute in get_object_attributes(session, name):
        if attribute['objectTypeAttribute']['name'] == 'Server Roles' or attribute['objectTypeAttribute']['name'] == 'Ansible host_vars':
            for attribute_value in attribute['objectAttributeValues']:
                key,value = attribute_value['displayValue'].split(":")
                hostvars[key.strip().lower()] = value.strip().lower()

    print json.dumps(hostvars, indent=4)

if __name__ == '__main__':
    session = requests.Session()

    # for performance reasons: get basic IDs only once
    schema_id = str(get_schema_id(session))
    objecttype_id = str(get_objecttype_id(session,schema_id))

    if len(sys.argv) == 2 and (sys.argv[1] == '--list'):
        print_grouplist(session, schema_id, objecttype_id)
    elif len(sys.argv) == 3 and (sys.argv[1] == '--host'):
        print_hostvars(session, sys.argv[2])
    else:
        print "Usage: %s --list or --host <hostname>" % sys.argv[0]
        sys.exit(1)
