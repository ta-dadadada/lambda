import os
import boto3
import json
import requests
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Slack の設定
SLACK_POST_URL = os.environ['slackPostURL']
SLACK_CHANNEL = os.environ['slackChannel']


# Budgets の設定
ACCOUNTID = os.environ['accountId']

MESSAGE_MAP = {
    'running': 'インスタンスが起動したよ',
    'stopped': 'インスタンスが停止したよ',
    'terminated': 'インスタンスが削除されたよ',
}


def lambda_handler(event, context):
    """
    {
  "version": "0",
  "id": "ee376907-2647-4179-9203-343cfb3017a4",
  "detail-type": "EC2 Instance State-change Notification",
  "source": "aws.ec2",
  "account": "123456789012",
  "time": "2015-11-11T21:30:34Z",
  "region": "us-east-1",
  "resources": [
    "arn:aws:ec2:us-east-1:123456789012:instance/i-abcd1111"
  ],
  "detail": {
    "instance-id": "i-abcd1111",
    "state": "running"
  }
}"""
    instance_id = event['detail']['instance-id']
    state = event['detail']['state']
    print(event)
    client = boto3.client('ec2')
    response = client.describe_instances(
        InstanceIds=[
            instance_id,
        ],
    )

    instance = response['Reservations'][0]['Instances'][0]
    fields = []

    # Name
    for tag in instance['Tags']:
        if tag['Key'] != 'Name':
            continue
        instance_name = tag['Value']
        fields.append({
            'title': 'Name',
            'value': instance_name,
            'short': True,
        })
        break

    # InstanceId
    fields.append({
        'title': 'インスタンス ID',
        'value': instance_id,
        'short': True,
    })

    # InstanceType
    fields.append({
        'title': 'インスタンスタイプ',
        'value': instance['InstanceType'],
        'short': True,
    })

    # AvailabilityZone
    fields.append({
        'title': 'アベイラビリティーゾーン',
        'value': instance['Placement']['AvailabilityZone'],
        'short': True,
    })

    # NetworkInterfaces
    for interfaces in instance['NetworkInterfaces']:
        idx = interfaces['Attachment']['DeviceIndex']
        for ip_addresses in interfaces['PrivateIpAddresses']:
            fields.append({
                'title': 'プライベート IP (eth{})'.format(idx),
                'value': ip_addresses.get('PrivateIpAddress'),
                'short': True,
            })
            fields.append({
                'title': 'パブリック IP (eth{})'.format(idx),
                'value': ip_addresses.get('Association', {}).get('PublicIp'),
                'short': True,
            })

    data = {
        'channel': SLACK_CHANNEL,
        'attachments': [{
            'pretext': MESSAGE_MAP.get(
                state, f'インスタンスの状態が変わったよ {state}'),
            'color': 'good',
            'fields': fields,
        }]
    }

    # SlackにPOST
    try:
        req = requests.post(SLACK_POST_URL, data=json.dumps(data))
        logger.info('Message posted to %s', data['channel'])
    except requests.exceptions.RequestException as e:
        logger.error('Request failed: %s', e)
