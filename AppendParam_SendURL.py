import json
import boto3
import botocore
import urllib3
import ast


class InsightVMScanner:
    def __init__(self):
        self.BASE_URL = "https://insightvm.matson.com"
        self.username = self.get_ssm_params("INSIGHTVM_USERNAME")
        self.password = self.get_ssm_params("INSIGHTVM_PASSWORD")
        self.engine_id = self.get_ssm_params("INSIGHTVM_ENGINE_ID")

    def get_ssm_params(self, ssm_param):
        print(f"SSMParam: {ssm_param}")
        ssm = boto3.client('ssm')
        response = ssm.get_parameters(
            Names=[ssm_param],WithDecryption=True
        )
        for parameter in response['Parameters']:
            return parameter['Value']

    def format_request_params(self, request_type, url_suffix, data):
        url = self.BASE_URL + url_suffix
        
        if data:
            encoded_data = json.dumps(data).encode('utf-8')
        else:
            encoded_data = data

        headers = urllib3.util.make_headers(basic_auth=f'{self.username}:{self.password}')
        headers['Content-Type'] = 'application/json'

        return url, encoded_data, headers

    def custom_request(self, request_type='GET', url_suffix='', data=None):
        url, encoded_data, headers = self.format_request_params(request_type, url_suffix, data)

        # Send request
        http = urllib3.PoolManager()
        r = http.request(request_type, url, body=encoded_data, headers=headers)

        status = r.status
        b_results = r.data
        results = ast.literal_eval(b_results.decode('utf-8'))
        
        return status, results

    def delete_site(self, site_id): 
        site_id = int(site_id)
        status, results = self.custom_request(request_type='DELETE', url_suffix=f'/api/3/sites/{site_id}')

        if not status == 200:
            raise SystemError(results['message'])
        
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
            InsightVMScanner().delete_site(site_id)
            
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ParameterNotFound':
            ssm.put_parameter(Name=paramName,Type='String', Value=amiID,Overwrite=True)
    return 'appended parameter %s with value %s.' % (paramName,amiID)