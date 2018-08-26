#!/usr/bin/env python2.7
import sys
import requests
from requests.auth import HTTPBasicAuth
try:
    import json
except ImportError:
    import simplejson as json

# import logging
# logging.basicConfig() # you need to initialize logging, otherwise you will not see anything from requests
# logging.getLogger().setLevel(logging.DEBUG)
# requests_log = logging.getLogger("urllib3")
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True

api_user = ''
api_password = ''
api_base_url = 'https://portal-test.visotech.com/jira/rest/insight/1.0'

schema_name = 'Infrastructure'
objecttype_name = 'Server'

limit = 10000      # number of hosts to list


def get_schema_id(session):
    '''authenticate and get schema id'''
    response_objectschemas = session.get(
        api_base_url + '/objectschema/list', auth=HTTPBasicAuth(api_user, api_password))
    for schema in response_objectschemas.json()['objectschemas']:
        if schema['name'] == schema_name:
            return schema['id']


def get_objecttypes(session, schema_id):
    '''get all objecttypes using schema id'''
    response_objecttypes = session.get(api_base_url + '/objectschema/' + schema_id + '/objecttypes/flat')
    return response_objecttypes.json()


def get_objecttypeId(session, schema_id, objecttypes, objecttype_name):
    '''get objecttypeId of specific objecttype_name using schema_id'''
    for objecttype in objecttypes:
        if objecttype['name'] == objecttype_name:
            return objecttype['id']


def get_objecttype_attributes(session, objecttypeId):
    '''get all objecttype attributes using objecttypeId'''
    response_objecttype_attributes = session.get(api_base_url + '/objecttype/' + objecttypeId + '/attributes')
    return response_objecttype_attributes.json()


def get_objecttype_attributeId(objecttype_attributes, attribute_name):
    for attribute in objecttype_attributes:
        if attribute['name'] == attribute_name:
            return attribute['id']


def get_objects(session, objecttypeId):
    response_objects = session.get(api_base_url + '/objecttype/' + objecttypeId + '/objects?limit=' + limit)
    return response_objects.json()


def get_object_id(session, objects, object_name):
    for object in objects:
        if object['name'] == object_name:
            return object['id']

def get_objectKey(session, objects, object_name):
    for object in objects:
        if object['name'] == object_name:
            return object['objectKey']



def get_object_attributes(session, object_id):
    '''use object id to get object attributes'''
    response_object_attributes = session.get(api_base_url + '/object/' + object_id + '/attributes')
    return response_object_attributes.json()


def get_objectEntries_with_iql(session, schema_id, objecttypeId, limit, iql, attributesToDisplayIds):
    '''get all objects of objecttypeId matching IQL expression, select attributesToDisplayIds'''

    post_data = {
        'objectSchemaId': int(schema_id),
        'objectTypeId': int(objecttypeId),
        'page': 1,
        'resultsPerPage': int(limit),
        'includeAttributes': 'true',
        'iql': iql,
        'attributesToDisplay': {
            'attributesToDisplayIds': attributesToDisplayIds
        }
    }
    response_objectEntries = session.post(
        api_base_url + '/object/navlist/iql', json=post_data)
    return response_objectEntries.json()


def print_list(session, schema_id):
    # initialize inventory as a dict
    inventory = {
        'insight': {
            'hosts': [],
            'vars': {
                'insight_schema': {
                    'id': int(schema_id)
                },
                'insight_objecttype': {
                    'attribute': {}
                },
            },
            'children': []
        },
        # _meta inventory for Ansible host_vars (see Development Guide for Ansible dynamic inventories: https://docs.ansible.com/ansible/2.6/dev_guide/developing_inventory.html)
        '_meta': {
            'hostvars': {}
        }
    }

    # get objecttypes of Server and Ansible group
    for objecttype in get_objecttypes(session, schema_id):
        if objecttype['name'] == 'Server':
            objecttype_id_server = objecttype['id']
        elif objecttype['name'] == 'Ansible Group':
            objecttype_id_group = objecttype['id']


    #############################
    # Servers and host_vars first
    #############################
    # for performance: use filtering via IQL and one single API Request to get all data
    # Display 'Server Roles', 'Ansible Hostvars' and 'Ansible Groups'

    # populate insight hostgroup with available attribute IDs
    objecttype_attributes_server = get_objecttype_attributes(session, str(objecttype_id_server))
    # populate all attributes and attribute ids for the server object in hostgroup insight
    # whitespaces are replaced with _ (makes life much easier in ansible)
    for attribute in objecttype_attributes_server:
        attribute_name = attribute['name'].replace(' ','_').lower()
        inventory['insight']['vars']['insight_objecttype']['attribute'][attribute_name] = { 'id': attribute['id'] }

        if 'referenceObjectType' in attribute:
            reference_object_type_name = attribute['referenceObjectType']['name'].replace(' ','_').lower()
            inventory['insight']['vars']['insight_objecttype']['attribute'][attribute_name]['reference_object_type'] = {
                'name': reference_object_type_name,
                'id': attribute['referenceObjectType']['id'],
                'object_schema_id': attribute['referenceObjectType']['objectSchemaId']
            }

    server_roles_id = get_objecttype_attributeId(objecttype_attributes_server, 'Server Roles')
    ansible_hostvars_id = get_objecttype_attributeId(objecttype_attributes_server, 'Ansible Hostvars')
    ansible_groups_id = get_objecttype_attributeId(objecttype_attributes_server, 'Ansible Groups')

    for entry in get_objectEntries_with_iql(session, schema_id, objecttype_id_server, limit, 'Status IN Active AND "Ansible Groups" IN ("tower")', [server_roles_id, ansible_hostvars_id, ansible_groups_id])['objectEntries']:
        hostname = entry['label']
        object_id = entry['id']
        object_key = entry['objectKey']

        # create basic _meta structure for hostname
        inventory['_meta']['hostvars'][hostname] = {
            'insight_object': {
                'id': int(object_id),
                'key': object_key
            }
        }

        for attribute in entry['attributes']:
            attribute_name = attribute['objectTypeAttribute']['name']

            # Server Roles
            if attribute_name == 'Server Roles':
                inventory['_meta']['hostvars'][hostname]['role'] = {}
                for attribute_value in attribute['objectAttributeValues']:
                    server_role = attribute_value['referencedObject']['name']
                    if ':' in server_role:
                        key, value = server_role.split(":")
                        inventory['_meta']['hostvars'][hostname]['role'][key.strip().lower()] = value.strip().lower()
                    else:
                        inventory['_meta']['hostvars'][hostname]['role'][server_role.strip().lower()] = None

            # Ansible Hostvars
            elif attribute_name == 'Ansible Hostvars':
                for attribute_value in attribute['objectAttributeValues']:
                    hostvars = attribute_value['referencedObject']['name']
                    if ':' in hostvars:
                        key, value = hostvars.split(":")
                        inventory['_meta']['hostvars'][hostname][key.strip().lower()] = value.strip().lower()
                    else:
                        inventory['_meta']['hostvars'][hostname][hostvars.strip().lower()] = None

           # populate Ansible Groups via references from server objects
            if attribute_name == 'Ansible Groups':
                if not attribute['objectAttributeValues']:
                    # if Ansible Groups has no attribute values (eg. this host not in a group)
                    # -> add to insight host group
                    inventory['insight']['hosts'].append(hostname)
                else:
                    # if Ansible Groups has attribute attribute values
                    # -> add this host to its Groups
                    for attribute_value in attribute['objectAttributeValues']:
                        ansible_group = attribute_value['referencedObject']['name']
                        inventory.setdefault(ansible_group, {'hosts': [], 'vars': {}, 'children': []})
                        inventory[ansible_group]['hosts'].append(hostname)


    ################################
    # Groupvars and Children second
    ################################

    objecttype_attributes_ansible_group = get_objecttype_attributes(session, str(objecttype_id_group))

    ansible_groupvars_id = get_objecttype_attributeId(objecttype_attributes_ansible_group, 'Ansible Groupvars')
    ansible_children_id = get_objecttype_attributeId(objecttype_attributes_ansible_group, 'Ansible Children')

    # Ansible Groupvars and Children
    for entry in get_objectEntries_with_iql(session, schema_id, objecttype_id_group, limit, '"Ansible Groupvars" IN ("tower")', [ansible_groupvars_id, ansible_children_id])['objectEntries']:
        ansible_group = entry['label']

        # create ansible_group, if it doesn't exist (eg. group has no hosts)
        inventory.setdefault(ansible_group, {'hosts': [], 'vars': {}, 'children': []})

        # append Ansible group to Insight group children
        inventory['insight']['children'].append(ansible_group)

        for attribute in entry['attributes']:
            attribute_name = attribute['objectTypeAttribute']['name']
            if attribute_name == 'Ansible Groupvars':
                for attribute_value in attribute['objectAttributeValues']:
                    ansible_groupvars = attribute_value['referencedObject']['name']
                    if ':' in ansible_groupvars:
                        key, value = ansible_groupvars.split(":")
                        inventory[ansible_group]['vars'][key.strip()] = value.strip()
                    else:
                        inventory[ansible_group]['vars'][ansible_groupvars.strip()] = None

            elif attribute_name == 'Ansible Children':
                for attribute_value in attribute['objectAttributeValues']:
                    ansible_children = attribute_value['referencedObject']['name']
                    inventory.setdefault(
                        ansible_group, {'hosts': [], 'vars': {}, 'children': []})
                    inventory[ansible_group]['children'].append(ansible_children)

    print json.dumps(inventory, indent=4)


if __name__ == '__main__':
    session = requests.Session()

    # for performance reasons: get schema ID only once
    schema_id = str(get_schema_id(session))

    if len(sys.argv) == 2 and (sys.argv[1] == '--list'):
        print_list(session, schema_id)
    else:
        print "Usage: %s --list" % sys.argv[0]
        sys.exit(1)
