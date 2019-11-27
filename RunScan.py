import urllib3
import boto3
import json
import os
import ast
import requests
import traceback

username = os.environ["INSIGHTVM_USERNAME"]
password = os.environ["INSIGHTVM_PASSWORD"]
engine_id = os.environ["INSIGHTVM_ENGINE_ID"]
BASE_URL = "https://insightvm.matson.com"
GOLDEN_SCAN_CREDENTIAL_NAME = 'GoldenAMI'


def create_site(engine_id='', site_name='', instance_ip=''):
    data =    {
        "description": "GoldenAMI API Test",
        "engineId": engine_id,
        "importance": "normal",
        "name": site_name,
        "scan": {
        "assets": {
            "includedTargets": {
                "addresses": [
                    instance_ip
                ]
            }
        },
        "scanTemplateId": "full-audit"
        }
    }

    url = BASE_URL + '/api/3/sites'
    headers = urllib3.util.make_headers(basic_auth=f'{username}:{password}')
    headers['Content-Type'] = 'application/json'
    response = requests.post(url=url, json=data, headers=headers, verify=False)

    json_response = json.loads(response.text)
    if not response.status_code == 201:
        raise SystemError(json_response['message'])

    dict_r = ast.literal_eval(response.text)
    site_id = dict_r['id']
    print(f"Site was created with site ID: {site_id}") 

    return site_id

def get_golden_ami_credential_id():
    url = BASE_URL + '/api/3/shared_credentials'
    headers = urllib3.util.make_headers(basic_auth=f'{username}:{password}')
    headers['Content-Type'] = 'application/json'
    response = requests.get(url=url, headers=headers, verify=False)

    json_response = json.loads(response.text)
    if not response.status_code == 200:
        raise SystemError(json_response['message'])

    dict_r = ast.literal_eval(response.text)
    resources = dict_r['resources']

    for resource in resources:
        if resource['name'] == GOLDEN_SCAN_CREDENTIAL_NAME:
            return resource['id']

    
def assign_shared_credential(site_id):
    credential_id = get_golden_ami_credential_id()
    url = BASE_URL + f'/api/3/sites/{site_id}/shared_credentials/{credential_id}/enabled'
    headers = urllib3.util.make_headers(basic_auth=f'{username}:{password}')
    headers['Content-Type'] = 'application/json'

    response = requests.put(url=url, headers=headers, verify=False, json="true")
    json_response = json.loads(response.text)

    if not response.status_code == 200:
        raise SystemError(json_response['message'])

    print(f"Shared credential ID: {credential_id} has been assigned to site ID: {site_id}")

def start_scan(site_id):
    url = BASE_URL + f'/api/3/sites/{site_id}/scans'
    headers = urllib3.util.make_headers(basic_auth=f'{username}:{password}')
    response = requests.post(url=url, headers=headers, verify=False)
    dict_r = ast.literal_eval(response.text)
    scan_id = dict_r['id']

    return scan_id

def delete_site(site_id):
    url = BASE_URL + f'/api/3/sites/{site_id}'
    headers = urllib3.util.make_headers(basic_auth=f'{username}:{password}')
    response = requests.delete(url=url, headers=headers, verify=False)
    json_response = json.loads(response.text)
    if not response.status_code == 200:
        raise SystemError(json_response['message'])
    
    print(f"Site {site_id} has been deleted")

def get_golden_instance_ip(instance_id):
    client = boto3.client('ec2')
    response = client.describe_instances(InstanceIds=[instance_id])
    golden_instance_ip = response['Reservations'][0]['Instances'][0]['PrivateIpAddress']
    print(golden_instance_ip)
    return golden_instance_ip

def lambda_handler(event, context=''):
    productOS = event.get('productOS')
    productName = event.get('productName')
    productVersion = event.get('productVersion')
    instance_id = event['instanceId']
    paramName='/GoldenAMI/'+productOS+'/'+productName+'/'+productVersion
    siteIDParam = paramName + '/siteID' 
    siteLinkParam = paramName + '/assessmentLink'
    
    ssm = boto3.client('ssm')

    try:
        golden_ip = get_golden_instance_ip(instance_id)
        site_id = create_site(engine_id=engine_id, site_name=paramName, instance_ip=golden_ip)
        assign_shared_credential(site_id)
        start_scan(site_id)

        link=  f"Link - https://insightvm.matson.com/site.jsp?siteid={site_id}"

        ssm.put_parameter(Name=siteIDParam, Type='String', Value=site_id, Overwrite=True)
        ssm.put_parameter(Name=siteLinkParam, Type='String', Value=link, Overwrite=True)
        
    except:
        print(traceback.format_exc())

    return "Scan started"