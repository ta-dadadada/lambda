import json
import os
import requests
from datetime import timezone, timedelta, datetime
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Slack関連の設定を環境変数から読み込む
SLACK_POST_URL = os.environ['slackPostURL']
SLACK_CHANNEL = os.environ['slackChannel']

# JSTを定義する
JST = timezone(timedelta(hours=9), 'JST')

JOB_STATUS_MAP = {
    #'InProgress': 'ジョブを実行してしておるぞ',
    'Completed': 'ジョブが終わったようじゃ',
    'Failed': 'ジョブに失敗しとるのう',
    # 'Stopping': None,
    'Stopped': 'ジョブが止められたの',
}


def gen_field(title: str, value: str, short: bool = False):
    return {'title': title, 'value': value, 'short': short}


def add_field(fields: list, title: str, value: str, short: bool = False):
    fields.append({'title': title, 'value': value, 'short': short})


def lambda_handler(event, context):
    detail = event['detail']
    status = detail['TrainingJobStatus']
    #print('[INFO]: status={} event={}'.format(status, event))
    if status not in JOB_STATUS_MAP:
        return
    resource_conf = detail['ResourceConfig']
    try:
        data = {
            'region': event['region'],
            'detail': event['detail'],
            'name': detail['TrainingJobName'],
            'status': detail['TrainingJobStatus'],
            'fail_reason': detail.get('FailureReason', None),
            'input_data_source': detail['InputDataConfig'],
            'output_data': detail['OutputDataConfig']['S3OutputPath'],
            'resource_conf': detail['ResourceConfig'],
            'instance_type': resource_conf['InstanceType'],
            'instance_counts': resource_conf['InstanceCount'],
            'start_at': detail.get('TrainingStartTime'),
            'end_at': detail.get('TrainingEndTime'),
        }
    except KeyError:
        data = {}
        logger.info(json.dumps(event))
    fields = [
        gen_field(
            f'{data["name"]} at {data["region"]}',
            JOB_STATUS_MAP[status]
        )]

    if data['start_at']:
        start_at = datetime.utcfromtimestamp(
            data['start_at'] / 1000
        ).astimezone(JST).strftime('%Y/%m/%d %H:%M:%S')
        add_field(fields, 'start', start_at, short=True)
    if data['end_at']:
        end_at = datetime.utcfromtimestamp(
            data['end_at'] / 1000
        ).astimezone(JST).strftime('%Y/%m/%d %H:%M:%S')
        add_field(fields, 'end', end_at, short=True)
    if data['fail_reason']:
        add_field(fields, 'ジョブの失敗原因', data['fail_reason'])
    add_field(
        fields,
        'インスタンス情報',
        f'type: {data["instance_type"]} counts: {data["instance_counts"]}')
    for src in data['input_data_source']:
        name = src.get('ChannelName')
        uri = src['DataSource'].get('S3DataSource', {}).get('S3Uri')
        add_field(fields, f'input: {name}', uri)
    if data['end_at']:
        add_field(fields, 'output', data['output_data'])
    atts = [{'fields': fields}]
    send_slack_message(None, attachments=atts)
    return {
        'statusCode': 200,
        'body': json.dumps(data)
    }


def send_slack_message(text: str, attachments: list = None):
    # Slackにメッセージを送信する

    if not attachments:
        data = {
            'channel': SLACK_CHANNEL,  # 送信先チャンネル
            'text': text,  # 内容
        }
    else:
        data = {
            'channel': SLACK_CHANNEL,  # 送信先チャンネル
            'text': text,
            'attachments': attachments,
        }
    try:
        req = requests.post(SLACK_POST_URL, data=json.dumps(data))
        logger.info('Message posted to %s', data['channel'])
    except requests.exceptions.RequestException as e:
        logger.error('Request failed: %s', e)
