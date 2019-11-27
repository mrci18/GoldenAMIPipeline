import boto3


class Ec2Actions:
    def __init__(self, tag=''):
        self.ec2 = boto3.client('ec2')
        self.tag = tag

    def get_true_tagged_instances(self):
        instance_ids_tagged_true = []

        response = self.ec2.describe_instances(
            Filters=[
                {
                    'Name': 'tag:'+ self.tag,
                    'Values': [
                        'true',
                    ]
                },
            ]
        )

        reservations = response['Reservations']
        for reservation in reservations:
            instance_id = reservation['Instances'][0]['InstanceId']
            instance_ids_tagged_true.append(instance_id)

        return instance_ids_tagged_true

    def terminate_assessment_tagged_instances(self):
        instance_ids_tagged_true = self.get_true_tagged_instances()
        self.ec2.terminate_instances(InstanceIds=instance_ids_tagged_true)
def lambda_handler(event, context=''):
    tag = event["tag"]

    Ec2Actions(tag=tag).terminate_assessment_tagged_instances()