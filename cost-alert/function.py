import json
import requests
import pytz
from dateutil import parser
import boto3
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Slack の設定
SLACK_POST_URL = os.environ['slackPostURL']
SLACK_CHANNEL = os.environ['slackChannel']

# Budgets の設定
BUDGET_NAME = os.environ['budgetName']
ACCOUNTID = os.environ['accountId']

client = boto3.client('budgets')
responce = client.describe_budget(
        AccountId=ACCOUNTID,
        BudgetName=BUDGET_NAME
)

#予算
budget = responce['Budget']['BudgetLimit']['Amount']
#現行
cost = responce['Budget']['CalculatedSpend']['ActualSpend']['Amount']
#予測
predicted = responce['Budget']['CalculatedSpend']['ForecastedSpend']['Amount']

utcdate = responce['ResponseMetadata']['HTTPHeaders']['date']
jst_date = parser.parse(utcdate).astimezone(pytz.timezone('Asia/Tokyo'))

budget = round(float(responce['Budget']['BudgetLimit']['Amount']))
cost = round(float(cost))
predicted = round(float(predicted))

date = jst_date.strftime('%Y-%m-%d')


def build_message(cost, predicted):
    if float(cost) >= budget:
        color = '#ff0000' #red
        emotion = '予算を超えてます！不要なリソースは削除しましょう！'

    elif float(predicted) > budget:
        color = 'warning' #yellow
        emotion = '予算を超えそうなので気をつけましょう。'
    else:
        color = 'good'    #green
        emotion = '予算内におさまってます。'

    text = f'{date} までのAWSの料金は ${cost} です。今月の予測料金は ${predicted} になりそうです。\n'
    text = text + emotion

    atachements = {'text': text, 'color': color}
    return atachements


def lambda_handler(event, context):
    content = build_message(cost,predicted)

    # SlackにPOSTする内容をセット
    slack_message = {
        'channel': SLACK_CHANNEL,
        'attachments': [content],
    }

    # SlackにPOST
    try:
        req = requests.post(SLACK_POST_URL, data=json.dumps(slack_message))
        logger.info('Message posted to %s', slack_message['channel'])
    except requests.exceptions.RequestException as e:
        logger.error('Request failed: %s', e)
