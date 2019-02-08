import json
import boto3
import os
import requests
from datetime import timezone, timedelta
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Slack関連の設定を環境変数から読み込む
SLACK_POST_URL = os.environ['slackPostURL']
SLACK_CHANNEL = os.environ['slackChannel']

# JSTを定義する
JST = timezone(timedelta(hours=9), 'JST')


def lambda_handler(event, context):
    # SageMakerが対応してるリージョン一覧を取得
    regions = boto3.Session().get_available_regions('sagemaker')

    # リージョンごとに実行
    notebooks_for_regions = {}
    training_jobs_for_regions = {}
    endpoints_for_regions = {}

    for region in regions:
        sm = boto3.client('sagemaker', region_name=region)

        # 起動中(InService)のインスタンスを取得する
        notebooks = sm.list_notebook_instances(
            StatusEquals='InService'
        )['NotebookInstances']
        if len(notebooks) > 0:
            notebooks_for_regions[region] = notebooks

        training_jobs = sm.list_training_jobs(
            StatusEquals='InProgress'
        )['TrainingJobSummaries']
        if len(training_jobs) > 0:
            training_jobs_for_regions[region] = training_jobs

        # 起動中のエンドポイントを取得する
        endpoints = sm.list_endpoints(
            StatusEquals='InService'
        )['Endpoints']
        if len(endpoints) > 0:
            endpoints_for_regions[region] = endpoints

    field_map = {
        'notebook': create_view_for_regions(notebooks_for_regions, create_notebook_field),
        'job': create_view_for_regions(training_jobs_for_regions, create_job_field),
        'endpoint': create_view_for_regions(endpoints_for_regions, create_endpoint_field),
    }
    color_map = {
        'notebook': '#439FE0',
        'job': 'warning',
        'endpoint': 'good',
    }
    # Slackにメッセージを送る
    atts = []
    for key, fields in field_map.items():
        if not fields:
            text = f'起動している {key} はないみたいじゃな。ぱないの！'
        else:
            text = f'{key} を見てきてやったぞ'
        atts.append({
            'pretext': text,  # 内容
            'fields': fields,
            'color': color_map.get(key, 'warning')
        })
    send_slack_message(None, attachments=atts)

    return {
        'statusCode': 200,
        'body': json.dumps('done')
    }


def create_view_for_regions(dic, func):
    # リージョン毎のデータ一覧用の表示を作る
    fields = []
    for region, data_list in dic.items():
        if len(data_list) == 0:
            continue
        for data in data_list:
            fields.append(func(data, region))
    return fields


def create_field(name: str, modified: str, region: str, short: bool = False) -> dict:
    return {'title': name, 'value': f'{region}: {modified} から起動しているようじゃ', 'short': short}


def create_notebook_field(data: dict, region: str) -> dict:
    name = data['NotebookInstanceName']
    modified = data['LastModifiedTime'].astimezone(JST).strftime('%Y/%m/%d %H:%M:%S')
    return create_field(name, modified, region)


def create_job_field(data: dict, region: str) -> dict:
    name = data['NotebookInstanceName']
    modified = data['LastModifiedTime'].astimezone(JST).strftime('%Y/%m/%d %H:%M:%S')
    return create_field(name, modified, region)


def create_endpoint_field(data: dict, region: str) -> dict:
    name = data['TrainingJobName']
    created = data['CreationTime'].astimezone(JST).strftime('%Y/%m/%d %H:%M:%S')
    return create_field(name, created, region)


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
