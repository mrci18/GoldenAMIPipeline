import urllib3
import boto3
import json
import ast
import traceback


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

    
    def create_site(self, site_name='', instance_ips=[]):
        data =    {
            "description": "GoldenAMI API",
            "engineId": self.engine_id,
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

        status, results = self.custom_request(request_type='POST', url_suffix='/api/3/sites', data=data)

        if not status == 201:
            raise SystemError(results['message'])

        site_id = results['id']
        print(f"Site was created with site ID: {site_id}") 

        return site_id

    def start_scan(self, site_id):
        status, results = self.custom_request(request_type='POST', url_suffix=f'/api/3/sites/{site_id}/scans')

        if not status == 201:
            raise SystemError(results['message'])

        scan_id = results['id']

        print(f"Scan started with scan ID: {scan_id}")
        return scan_id

    def main(self, site_name='', instance_ips=[]):
        """This lambda assumes that sites created will automically have shared credentials needed enabled on insightvm console"""
        site_id = self.create_site(site_name=site_name, instance_ips=instance_ips)
        self.start_scan(site_id)

        return site_id

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

        site_id = InsightVMScanner().main(site_name=paramName, instance_ips=[golden_ip])

        link=  f"Link - https://insightvm.matson.com/site.jsp?siteid={site_id}"

        ssm.put_parameter(Name=siteIDParam, Type='String', Value=site_id, Overwrite=True)
        ssm.put_parameter(Name=siteLinkParam, Type='String', Value=link, Overwrite=True)
        
    except:
        print(traceback.format_exc())

    return "Scan started"
