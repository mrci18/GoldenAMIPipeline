
import json
import urllib.parse
import urllib3
import requests
import boto3
import ast
import time
import os

username = os.environ["INSIGHTVM_USERNAME"]
password = os.environ["INSIGHTVM_PASSWORD"]
#Engine ID must be set, it can't be found via API if engine connects engine to console
engine_id = os.environ["INSIGHTVM_ENGINE_ID"]
BASE_URL = "https://insightvm.matson.com"
GOLDEN_SCAN_CREDENTIAL_NAME = 'GoldenAMI'

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
    site_id = int(site_id)
    url = BASE_URL + f'/api/3/sites/{site_id}'
    headers = urllib3.util.make_headers(basic_auth=f'{username}:{password}')
    response = requests.delete(url=url, headers=headers, verify=False)
    json_response = json.loads(response.text)
    if not response.status_code == 200:
        raise SystemError(json_response['message'])
    
    print(f"Site {site_id} has been deleted")

def create_site(engine_id='', site_name='', instance_ips=[]):
    #Figure out better way to set engineID
    # Change IP to instance IP
    data =    {
        "description": "GoldenAMI API Test",
        "engineId": engine_id,
        "importance": "normal",
        "name": site_name,
        "scan": {
        "assets": {
            "includedTargets": {
                "addresses": instance_ips
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

def lambda_handler(event, context):
    amisParamName = event['AMIsParamName']
    instanceType = event['instanceType']
    region=os.environ['AWS_DEFAULT_REGION']
    ec2 = boto3.client('ec2',region)
    ssm = boto3.client('ssm',region)
    sfn = boto3.client('stepfunctions')
    amisJson =  ssm.get_parameter(Name=amisParamName)['Parameter']['Value']
    items = amisJson.split(',')
    instance_ips = []

    for entry in items:
        images= ec2.describe_images(ImageIds=[entry],DryRun=False)
        if 'Tags' in images['Images'][0]:
            tags = images['Images'][0]['Tags']
            tags.append({'Key': 'continuous-assessment-instance', 'Value': 'true'})
            response = ec2.run_instances(ImageId=entry,SubnetId='subnet-07904fd190b40c64c',SecurityGroupIds=['sg-01cc53c9994b04649'],InstanceType=instanceType,DryRun=False,MaxCount=1,MinCount=1,TagSpecifications=[{'ResourceType': 'instance','Tags': tags}])
        else:
            response = ec2.run_instances(ImageId=entry,SubnetId='subnet-07904fd190b40c64c',SecurityGroupIds=['sg-01cc53c9994b04649'],InstanceType=instanceType,DryRun=False,MaxCount=1,MinCount=1,TagSpecifications=[{'ResourceType': 'instance','Tags': [{'Key': 'continuous-assessment-instance', 'Value': 'true'},{'Key': 'AMI-Type', 'Value': 'Golden'}]}])

        private_ip = response['Instances'][0]['InstanceId']['PrivateIpAddress']
        instance_ips.append(private_ip)

    old_site_id = ssm.get_parameter(Name='/GoldenAMI/ContinuousScan/siteID')['Parameter']['Value']
    if old_site_id != "0":
        delete_site(old_site_id)
    site_id = create_site(engine_id, '/GoldenAMI/ContinuousScan', instance_ips)
    assign_shared_credential(site_id)
    start_scan(site_id)

    link=  f"Link - https://insightvm.matson.com/site.jsp?siteid={site_id}"

    ssm.put_parameter(Name='/GoldenAMI/ContinuousScan/siteID', Type='String', Value=site_id, Overwrite=True)
    ssm.put_parameter(Name='/GoldenAMI/ContinuousScan/assessmentLink', Type='String', Value=link, Overwrite=True)

    #Replace stateMachineArn with StepFunctionsStateMachine Arn
    sfn.start_execution(stateMachineArn='string', input="{\"tag\" : \"continuous-assessment-instance\"}")
    
    return 'Assessment started'