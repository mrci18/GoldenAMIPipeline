import os
import json
import boto3
import botocore
import urllib3
import requests

username = os.environ["INSIGHTVM_USERNAME"]
password = os.environ["INSIGHTVM_PASSWORD"]
BASE_URL = "https://insightvm.matson.com"


def delete_site(site_id):
    site_id = int(site_id)
    url = BASE_URL + f'/api/3/sites/{site_id}'
    headers = urllib3.util.make_headers(basic_auth=f'{username}:{password}')
    response = requests.delete(url=url, headers=headers, verify=False)
    json_response = json.loads(response.text)
    if not response.status_code == 200:
        raise SystemError(json_response['message'])
    
    print(f"Site {site_id} has been deleted")

def lambda_handler(event, context):
    paramName =event['parameterName']
    amiIDVal=event['valueToBeCreatedOrAppended']
    print(amiIDVal)
    amiID=amiIDVal.replace("\\r\\n","\n")
    print(amiID)
    ssm = boto3.client('ssm')
    try:
        AMIIdsParam =ssm.get_parameter(Name=paramName)
        AMIIds=AMIIdsParam['Parameter']['Value']
        AMIIds= AMIIds+','+ amiID
        ssm.put_parameter(Name=paramName,Type='String', Value=AMIIds,Overwrite=True)

        if 'latest' in paramName:
            siteIDParamName = paramName.replace('latest', 'siteID')
            site_id = ssm.get_parameter(Name=siteIDParamName)
            delete_site(site_id)
            
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ParameterNotFound':
            ssm.put_parameter(Name=paramName,Type='String', Value=amiID,Overwrite=True)
    return 'appended parameter %s with value %s.' % (paramName,amiID)